from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render

from cart.models import Cart


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Display items in the user's cart with prices, availability, and totals.
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

    total_price = 0
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

        item.subtotal = item.unit_price * item.quantity

        if item.is_available:
            total_price += item.subtotal

        items_data.append({
            "id": item.id,
            "product_id": product.id,
            "product_name": product.name,
            "variant_id": variant.id,
            "quantity": item.quantity,
            "unit_price": str(item.unit_price),
            "subtotal": str(item.subtotal),
            "stock_quantity": variant.stock_quantity,
            "is_available": item.is_available,
        })

    if wants_json(request):
        return JsonResponse(
            {
                "success": True,
                "cart_id": cart.id,
                "items": items_data,
                "total_price": str(total_price),
                "item_count": len(items_data),
                "has_unavailable_items": any(
                    not item["is_available"] for item in items_data
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