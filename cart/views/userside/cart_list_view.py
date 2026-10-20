from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render
from django.utils import timezone

from cart.models import Cart
from products.models import ProductOffer
from categories.models import CategoryOffer


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Display cart items with applicable offers, availability, and totals.
@login_required
def cart_list(request):

    if request.method != "GET":
        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Only GET requests are allowed."
                },
                status=405
            )

        return HttpResponseNotAllowed(["GET"])

    cart, created = Cart.objects.get_or_create(
        user=request.user
    )

    cart_items = cart.items.select_related(
        "product_variant",
        "product_variant__product",
        "product_variant__product__category"
    ).prefetch_related(
        "product_variant__images"
    )

    current_time = timezone.now()
    total_price = Decimal("0.00")
    items_data = []

    for item in cart_items:

        variant = item.product_variant
        product = variant.product
        category = product.category

        item.is_available = (
            variant.is_active
            and product.is_active
            and category.is_active
            and variant.stock_quantity > 0
        )

        # Use the variant's regular price as the base price.
        regular_price = variant.price

        # Find the highest currently active product offer.
        product_offer = ProductOffer.objects.filter(
            product=product,
            is_active=True,
            start_date__lte=current_time,
            end_date__gte=current_time
        ).order_by("-discount_value").first()

        # Find the highest currently active category offer.
        category_offer = CategoryOffer.objects.filter(
            category=category,
            is_active=True,
            start_date__lte=current_time,
            end_date__gte=current_time
        ).order_by("-discount_value").first()

        # Select the offer with the highest discount percentage.
        applicable_offer = None

        if product_offer and category_offer:
            if product_offer.discount_value >= category_offer.discount_value:
                applicable_offer = product_offer
            else:
                applicable_offer = category_offer

        elif product_offer:
            applicable_offer = product_offer

        elif category_offer:
            applicable_offer = category_offer

        # Calculate the discounted price, if an offer exists.
        if applicable_offer:
            discount_amount = (
                regular_price
                * applicable_offer.discount_value
                / Decimal("100")
            )

            item.unit_price = (
                regular_price - discount_amount
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )

            item.discount_percentage = applicable_offer.discount_value
            item.regular_price = regular_price

        else:
            item.unit_price = regular_price
            item.discount_percentage = Decimal("0.00")
            item.regular_price = regular_price

        # Calculate the subtotal using the final unit price.
        item.subtotal = (
            item.unit_price * item.quantity
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        if item.is_available:
            total_price += item.subtotal

        items_data.append({
            "id": item.id,
            "product_id": product.id,
            "product_name": product.name,
            "variant_id": variant.id,
            "quantity": item.quantity,
            "regular_price": str(item.regular_price),
            "unit_price": str(item.unit_price),
            "discount_percentage": str(item.discount_percentage),
            "subtotal": str(item.subtotal),
            "stock_quantity": variant.stock_quantity,
            "is_available": item.is_available,
        })

    total_price = total_price.quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )

    if wants_json(request):
        return JsonResponse(
            {
                "success": True,
                "cart_id": cart.id,
                "items": items_data,
                "total_price": str(total_price),
                "item_count": len(items_data),
                "has_unavailable_items": any(
                    not item["is_available"]
                    for item in items_data
                ),
            },
            status=200
        )

    return render(
        request,
        "userside/cart.html",
        {
            "cart": cart,
            "cart_items": cart_items,
            "total_price": total_price,
        }
    )