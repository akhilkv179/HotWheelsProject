 
from decimal import Decimal
from uuid import uuid4

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from accounts.models import Address
from cart.models import Cart, CartItem
from products.models import ProductVariant
from orders.models import Order, OrderItem, OrderAddress, OrderStatusHistory


@login_required
def checkout(request):
    cart = Cart.objects.filter(user=request.user).first()

    if not cart or not cart.items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect("cart_list")

    addresses = Address.objects.filter(user=request.user)
    selected_address_id = request.GET.get("address")
    selected_address = addresses.filter(id=selected_address_id).first() if selected_address_id else addresses.filter(is_default=True).first()

    if selected_address is None:
        selected_address = addresses.first()

    cart_items = list(
        CartItem.objects.filter(cart=cart).select_related(
            "product_variant",
            "product_variant__product",
        )
    )

    subtotal = Decimal("0.00")

    for item in cart_items:
        subtotal += item.product_variant.price * item.quantity

    shipping_amount = Decimal("0.00") if subtotal >= Decimal("1000.00") else Decimal("50.00")
    discount_amount = Decimal("0.00")
    total_amount = subtotal - discount_amount + shipping_amount

    context = {
        "cart_items": cart_items,
        "addresses": addresses,
        "selected_address": selected_address,
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "shipping_amount": shipping_amount,
        "total_amount": total_amount,
    }

    if request.method == "GET":
        return render(request, "userside/checkout.html", context)

    if not selected_address:
        messages.error(request, "Please add a delivery address.")
        return redirect("checkout")

    if request.POST.get("address_id"):
        selected_address = addresses.filter(
            id=request.POST.get("address_id")
        ).first()

        if not selected_address:
            messages.error(request, "Please select a valid address.")
            return redirect("checkout")

    try:
        with transaction.atomic():
            locked_items = list(
                CartItem.objects.filter(cart=cart)
                .select_related("product_variant", "product_variant__product")
                .order_by("product_variant_id")
            )

            if not locked_items:
                messages.error(request, "Your cart is empty.")
                return redirect("cart_list")

            variants = {
                variant.id: variant
                for variant in ProductVariant.objects.select_for_update().filter(
                    id__in=[item.product_variant_id for item in locked_items]
                ).select_related("product", "product__category")
            }

            subtotal = Decimal("0.00")

            for item in locked_items:
                variant = variants.get(item.product_variant_id)

                if (
                    not variant
                    or not variant.is_active
                    or not variant.product.is_active
                    or variant.product.is_deleted
                    or not variant.product.category.is_active
                ):
                    raise ValueError("A product in your cart is unavailable.")

                if item.quantity < 1 or variant.stock_quantity < item.quantity:
                    raise ValueError(
                        f"Insufficient stock for {variant.product.name}."
                    )

                item.unit_price = variant.price
                subtotal += variant.price * item.quantity

            shipping_amount = Decimal("0.00") if subtotal >= Decimal("1000.00") else Decimal("50.00")
            discount_amount = Decimal("0.00")
            total_amount = subtotal - discount_amount + shipping_amount

            order = Order.objects.create(
                user=request.user,
                address=selected_address,
                order_number=f"HW-{uuid4().hex[:12].upper()}",
                status="pending",
                subtotal=subtotal,
                discount_amount=discount_amount,
                shipping_amount=shipping_amount,
                total_amount=total_amount,
                delivery_method="Cash on Delivery",
            )

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

            for item in locked_items:
                variant = variants[item.product_variant_id]
                line_total = variant.price * item.quantity

                OrderItem.objects.create(
                    order=order,
                    product_variant=variant,
                    product_name=variant.product.name,
                    quantity=item.quantity,
                    unit_price=variant.price,
                    total_price=line_total,
                    discount_amount=Decimal("0.00"),
                )

                variant.stock_quantity -= item.quantity
                variant.save(update_fields=["stock_quantity", "updated_at"])

            OrderStatusHistory.objects.create(
                order=order,
                status="pending",
            )

            CartItem.objects.filter(cart=cart).delete()

    except ValueError as error:
        messages.error(request, str(error))
        return redirect("checkout")

    messages.success(request, "Your order has been placed successfully.")
    return redirect("order_success", order_number=order.order_number)


@login_required
def order_success(request, order_number):
    order = get_object_or_404(
        Order,
        order_number=order_number,
        user=request.user,
    )

    return redirect("checkout")

