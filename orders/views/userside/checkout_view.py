
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4
from categories.models import CategoryOffer
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from accounts.models import Address
from cart.models import Cart, CartItem
from products.models import ProductVariant
from orders.models import Order, OrderItem, OrderAddress, OrderStatusHistory
from payments.models import Payment
from wallet.models import Wallet
from wallet.services.transaction_service import process_wallet_transaction
from coupons.services import (
    calculate_coupon_discount,
    record_coupon_usage,
)


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")



# Find the currently valid offer for a product.
def get_active_product_offer(product, current_time):
    return product.offers.filter(
        is_active=True,
        start_date__lte=current_time,
        end_date__gte=current_time,
    ).order_by("-discount_value").first()


# Find the currently valid offer for a category.
def get_active_category_offer(category, current_time):
    return CategoryOffer.objects.filter(
        category=category,
        is_active=True,
        start_date__lte=current_time,
        end_date__gte=current_time,
    ).order_by("-discount_value").first()


# Compare product and category offers and apply only the larger discount.
def calculate_item_offer(item, current_time):
    variant = item.product_variant
    product = variant.product
    category = product.category

    product_offer = get_active_product_offer(
        product,
        current_time,
    )

    category_offer = (
        get_active_category_offer(category, current_time)
        if category
        else None
    )

    # Product offers take precedence when both discounts are equal.
    offer = product_offer
    offer_type = "product" if product_offer else None

    if (
        category_offer
        and (
            offer is None
            or category_offer.discount_value > offer.discount_value
        )
    ):
        offer = category_offer
        offer_type = "category"

    original_unit_price = variant.price

    if offer:
        discount_per_unit = (
            original_unit_price * offer.discount_value / Decimal("100")
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        offer_name = offer.offer_name
        offer_percentage = offer.discount_value
    else:
        discount_per_unit = Decimal("0.00")
        offer_name = None
        offer_percentage = None

    discounted_unit_price = original_unit_price - discount_per_unit
    line_discount = discount_per_unit * item.quantity
    original_line_total = original_unit_price * item.quantity
    discounted_line_total = original_line_total - line_discount

    # Attach calculated values for checkout templates and JSON responses.
    item.original_unit_price = original_unit_price
    item.discount_per_unit = discount_per_unit
    item.discounted_unit_price = discounted_unit_price
    item.item_discount_total = line_discount
    item.original_line_total = original_line_total
    item.discounted_line_total = discounted_line_total
    item.offer_name = offer_name
    item.offer_percentage = offer_percentage
    item.offer_type = offer_type

    return item



# Process checkout, validate inventory, handle payment, and create the order.
@login_required
def checkout(request):
    # Allow only GET and POST requests.
    if request.method not in ["GET", "POST"]:
        if wants_json(request):
            return JsonResponse(
                {"error": "Only GET and POST requests are allowed."},
                status=405,
            )
        return HttpResponseNotAllowed(["GET", "POST"])

    # Find the logged-in user's cart.
    cart = Cart.objects.filter(user=request.user).first()

    if not cart or not cart.items.exists():
        if wants_json(request):
            return JsonResponse(
                {"error": "Your cart is empty."},
                status=400,
            )
        messages.error(request, "Your cart is empty.")
        return redirect("cart_list")

    # Find the user's saved addresses and determine the selected address.
    addresses = Address.objects.filter(user=request.user)
    selected_address_id = request.GET.get("address")
    selected_address = (
        addresses.filter(id=selected_address_id).first()
        if selected_address_id
        else addresses.filter(is_default=True).first()
    )

    if selected_address is None:
        selected_address = addresses.first()

    # Get cart items that currently have stock for initial checkout display.
    cart_items = list(
        CartItem.objects.filter(
            cart=cart,
            product_variant__stock_quantity__gt=0,
        ).select_related(
            "product_variant",
            "product_variant__product",
            "product_variant__product__category",
        )
    )

    # Calculate the initial checkout totals, including product offers.
    current_time = timezone.now()
    subtotal = Decimal("0.00")
    discount_amount = Decimal("0.00")

    for item in cart_items:
        calculate_item_offer(item, current_time)
        subtotal += item.original_line_total
        discount_amount += item.item_discount_total

    discounted_subtotal = subtotal - discount_amount

    # Preserve the existing free-shipping threshold based on original subtotal.
    shipping_amount = (
        Decimal("0.00")
        if subtotal >= Decimal("1000.00")
        else Decimal("50.00")
    )

    total_amount = discounted_subtotal + shipping_amount

    # Prepare the data needed by the checkout template.
    context = {
        "cart_items": cart_items,
        "addresses": addresses,
        "selected_address": selected_address,
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "discounted_subtotal": discounted_subtotal,
        "shipping_amount": shipping_amount,
        "total_amount": total_amount,
    }

    # Return checkout information for GET requests.
    if request.method == "GET":
        if wants_json(request):
            return JsonResponse(
                {
                    "cart_items": [
                        {
                            "cart_item_id": item.id,
                            "product_variant_id": item.product_variant_id,
                            "product_name": item.product_variant.product.name,
                            "quantity": item.quantity,
                            "unit_price": str(item.original_unit_price),
                            "offer_name": item.offer_name,
                            "offer_percentage": (
                                str(item.offer_percentage)
                                if item.offer_percentage is not None
                                else None
                            ),
                            "discount_per_unit": str(item.discount_per_unit),
                            "discount_amount": str(item.item_discount_total),
                            "discounted_unit_price": str(
                                item.discounted_unit_price
                            ),
                            "line_total": str(item.discounted_line_total),
                            "stock_quantity": (
                                item.product_variant.stock_quantity
                            ),
                        }
                        for item in cart_items
                    ],
                    "addresses": [
                        {
                            "id": address.id,
                            "full_name": address.full_name,
                            "address_line1": address.address_line1,
                            "city": address.city,
                            "state": address.state,
                            "postal_code": address.postal_code,
                            "is_default": address.is_default,
                        }
                        for address in addresses
                    ],
                    "selected_address_id": (
                        selected_address.id if selected_address else None
                    ),
                    "subtotal": str(subtotal),
                    "discount_amount": str(discount_amount),
                    "discounted_subtotal": str(discounted_subtotal),
                    "shipping_amount": str(shipping_amount),
                    "total_amount": str(total_amount),
                },
                status=200,
            )

        return render(request, "userside/checkout.html", context)

    # Identify and validate the payment method selected by the customer.
    payment_method = request.POST.get(
        "payment_method", "cod"
    ).strip().lower()

    if payment_method not in ("cod", "razorpay", "wallet"):
        error_message = "Please select a valid payment method."

        if wants_json(request):
            return JsonResponse({"error": error_message}, status=400)

        messages.error(request, error_message)
        return redirect("checkout")

    # Razorpay must use the JSON checkout flow so payment can start afterward.
    if payment_method == "razorpay" and not wants_json(request):
        messages.error(
            request,
            "Please enable JavaScript to complete online payment.",
        )
        return redirect("checkout")

    # Store the selected payment method using the existing Order field.
    if payment_method == "razorpay":
        delivery_method = "Razorpay"
    elif payment_method == "wallet":
        delivery_method = "Wallet"
    else:
        delivery_method = "Cash on Delivery"

    # Validate the delivery address before creating an order.
    if not selected_address:
        error_message = "Please add a delivery address."

        if wants_json(request):
            return JsonResponse({"error": error_message}, status=400)

        messages.error(request, error_message)
        return redirect("checkout")

    # Use the address selected in the submitted checkout form.
    if request.POST.get("address_id"):
        selected_address = addresses.filter(
            id=request.POST.get("address_id")
        ).first()

        if not selected_address:
            error_message = "Please select a valid address."

            if wants_json(request):
                return JsonResponse({"error": error_message}, status=400)

            messages.error(request, error_message)
            return redirect("checkout")

    # Read the coupon code submitted with the checkout request.
    coupon_code = request.POST.get("coupon_code", "").strip()

    try:
        # Keep order creation, stock changes, coupon usage, and wallet payment atomic.
        with transaction.atomic():
            # Reload cart items before processing the order.
            locked_items = list(
                CartItem.objects.filter(cart=cart)
                .select_related(
                    "product_variant",
                    "product_variant__product",
                    "product_variant__product__category",
                )
                .order_by("product_variant_id")
            )

            if not locked_items:
                raise ValueError("Your cart is empty.")

            # Lock the product variants to avoid overselling available stock.
            variants = {
                variant.id: variant
                for variant in ProductVariant.objects.select_for_update()
                .filter(
                    id__in=[
                        item.product_variant_id for item in locked_items
                    ]
                )
                .select_related("product", "product__category")
            }

            current_time = timezone.now()
            subtotal = Decimal("0.00")
            discount_amount = Decimal("0.00")

            # Validate every item and recalculate current offer prices.
            for item in locked_items:
                variant = variants.get(item.product_variant_id)

                if (
                    not variant
                    or not variant.is_active
                    or not variant.product.is_active
                    or variant.product.is_deleted
                    or not variant.product.category
                    or not variant.product.category.is_active
                    or variant.product.category.is_deleted
                ):
                    raise ValueError(
                        "A product in your cart is unavailable."
                    )

                if (
                    item.quantity < 1
                    or variant.stock_quantity < item.quantity
                ):
                    raise ValueError(
                        f"Insufficient stock for {variant.product.name}."
                    )

                # Calculate discounts using the latest variant price and offer.
                calculate_item_offer(item, current_time)

                subtotal += item.original_line_total
                discount_amount += item.item_discount_total

            # Calculate the subtotal after product offer discounts.
            discounted_subtotal = subtotal - discount_amount

            # Preserve the existing free-shipping threshold based on original subtotal.
            shipping_amount = (
                Decimal("0.00")
                if subtotal >= Decimal("1000.00")
                else Decimal("50.00")
            )

            # Apply the coupon to the discounted subtotal, before shipping.
            coupon = None
            coupon_discount = Decimal("0.00")

            if coupon_code:
                coupon, coupon_discount = calculate_coupon_discount(
                    code=coupon_code,
                    eligible_subtotal=discounted_subtotal,
                )

            # Combine product-offer and coupon discounts for the order record.
            final_discount_amount = discount_amount + coupon_discount

            total_amount = (
                discounted_subtotal
                - coupon_discount
                + shipping_amount
            )

            # Lock and validate the wallet before creating a wallet-paid order.
            wallet = None

            if payment_method == "wallet":
                wallet = (
                    Wallet.objects.select_for_update()
                    .filter(user=request.user, is_active=True)
                    .first()
                )

                if wallet is None:
                    raise ValueError(
                        "Your wallet is unavailable. Please try another payment method."
                    )

                if wallet.balance < total_amount:
                    raise ValueError(
                        "Insufficient wallet balance. Please add funds or choose another payment method."
                    )

            # Wallet orders are confirmed immediately after the debit succeeds.
            order_status = (
                "confirmed" if payment_method == "wallet" else "pending"
            )

            # Create the order with product and coupon discounts.
            order = Order.objects.create(
                user=request.user,
                address=selected_address,
                order_number=f"HW-{uuid4().hex[:12].upper()}",
                status=order_status,
                subtotal=subtotal,
                discount_amount=final_discount_amount,
                coupon=coupon,
                shipping_amount=shipping_amount,
                total_amount=total_amount,
                delivery_method=delivery_method,
            )

            # Save a snapshot of the selected address for this order.
            OrderAddress.objects.create(
                order=order,
                address_label=selected_address.get_address_type_display(),
                full_name=selected_address.full_name,
                phone=selected_address.phone,
                address_line1=selected_address.address_line1,
                address_line2=selected_address.address_line2,
                city=selected_address.city,
                state=selected_address.state,
                country="India",
                pin=selected_address.postal_code,
                custom_label=selected_address.landmark,
            )

            # Save order items with original prices and their offer discounts.
            for item in locked_items:
                variant = variants[item.product_variant_id]

                OrderItem.objects.create(
                    order=order,
                    product_variant=variant,
                    product_name=variant.product.name,
                    quantity=item.quantity,
                    unit_price=item.original_unit_price,
                    total_price=item.discounted_line_total,
                    discount_amount=item.item_discount_total,
                )

                # Deduct the purchased quantity from stock.
                variant.stock_quantity -= item.quantity
                variant.save(
                    update_fields=["stock_quantity", "updated_at"]
                )

            # Deduct from the wallet and record the transaction via the service.
            if payment_method == "wallet":
                wallet_transaction_id = f"WALLET-{uuid4().hex.upper()}"

                wallet_transaction = process_wallet_transaction(
                    wallet_id=wallet.pk,
                    amount=total_amount,
                    transaction_type="debit",
                    transaction_id=wallet_transaction_id,
                    reference_id=order.order_number,
                )

                # Record the successful wallet payment against this order.
                Payment.objects.create(
                    order=order,
                    amount=total_amount,
                    payment_method="wallet",
                    status="paid",
                    transaction_id=wallet_transaction.transaction_id,
                    paid_at=timezone.now(),
                )

            # Record the initial order status.
            OrderStatusHistory.objects.create(
                order=order,
                status=order_status,
            )

            # Record coupon usage inside the same transaction as the order.
            # If checkout fails, the usage record and usage count roll back too.
            if coupon is not None:
                record_coupon_usage(
                    coupon=coupon,
                    order=order,
                    user=request.user,
                    discount_amount=coupon_discount,
                )

            # Empty the cart only after order processing succeeds.
            CartItem.objects.filter(cart=cart).delete()

    except (ValueError, ValidationError) as error:
        if isinstance(error, ValidationError):
            error_message = (
                error.messages[0]
                if error.messages
                else "Unable to process checkout."
            )
        else:
            error_message = str(error)

        if wants_json(request):
            return JsonResponse({"error": error_message}, status=400)

        messages.error(request, error_message)
        return redirect("checkout")

    # Return order details and tell the frontend whether payment is required.
    if wants_json(request):
        is_online_payment = payment_method == "razorpay"

        return JsonResponse(
            {
                "message": (
                    "Order created. Continue to payment."
                    if is_online_payment
                    else "Your order has been placed successfully."
                ),
                "order_number": order.order_number,
                "order_status": order.status,
                "payment_method": payment_method,
                "payment_required": is_online_payment,
                "subtotal": str(order.subtotal),
                "discount_amount": str(order.discount_amount),
                "discounted_subtotal": str(
                    order.subtotal - order.discount_amount
                ),
                "coupon_code": coupon.code if coupon else None,
                "coupon_discount": str(coupon_discount),
                "shipping_amount": str(order.shipping_amount),
                "total_amount": str(order.total_amount),
            },
            status=201,
        )

    # Show a success message and redirect normal browser requests.
    messages.success(
        request,
        "Your order has been placed successfully.",
    )

    return redirect(
        "order_success",
        order_number=order.order_number,
    )


# Display the confirmation page for an order owned by the logged-in user.
@login_required
def order_success(request, order_number):
    # Find the order belonging to the current user.
    order = get_object_or_404(
        Order,
        order_number=order_number,
        user=request.user,
    )

    # Do not display Razorpay orders as successful before payment is verified.
    if (
        order.delivery_method == "Razorpay"
        and not order.payments.filter(status="paid").exists()
    ):
        error_message = "Payment has not been confirmed for this order yet."

        if wants_json(request):
            return JsonResponse({"error": error_message}, status=409)

        messages.error(request, error_message)
        return redirect(
            "user_order_detail",
            order_number=order.order_number,
        )

    # Return order confirmation details to JSON clients.
    if wants_json(request):
        return JsonResponse(
            {
                "message": "Your order has been placed successfully.",
                "order_number": order.order_number,
                "order_status": order.status,
                "subtotal": str(order.subtotal),
                "discount_amount": str(order.discount_amount),
                "total_amount": str(order.total_amount),
                "created_at": order.created_at.isoformat(),
            },
            status=200,
        )

    # Render the confirmation page for normal browser requests.
    return render(
        request,
        "userside/order_success.html",
        {"order": order},
    )
