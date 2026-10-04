from django.shortcuts import render, redirect
from django.contrib import messages

from cart.models import Cart


MAX_QUANTITY = 5


def checkout(request):

    if not request.user.is_authenticated:
        return redirect("login")

    cart = Cart.objects.filter(
        user=request.user
    ).first()

    if not cart:
        messages.error(request, "Your cart is empty.")
        return redirect("cart_list")

    cart_items = cart.items.select_related(
        "product_variant",
        "product_variant__product",
        "product_variant__product__category"
    )

    if not cart_items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect("cart_list")

    for item in cart_items:

        variant = item.product_variant
        product = variant.product
        category = product.category

        if (
            not variant.is_active
            or not product.is_active
            or not category.is_active
        ):
            messages.error(
                request,
                "Your cart contains an unavailable product."
            )
            return redirect("cart_list")

        if variant.stock_quantity <= 0:
            messages.error(
                request,
                "Your cart contains an out-of-stock product."
            )
            return redirect("cart_list")

        if item.quantity > MAX_QUANTITY:
            messages.error(
                request,
                f"You can add a maximum of {MAX_QUANTITY} items."
            )
            return redirect("cart_list")

        if item.quantity > variant.stock_quantity:
            messages.error(
                request,
                "The quantity of a product in your cart exceeds available stock."
            )
            return redirect("cart_list")

    return render(
        request,
        "userside/checkout.html",
        {
            "cart": cart,
            "cart_items": cart_items,
        }
    )