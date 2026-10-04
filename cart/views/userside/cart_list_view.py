from django.shortcuts import render, redirect

from cart.models import Cart


def cart_list(request):

    if not request.user.is_authenticated:
        return redirect("login")

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

    return render(
        request,
        "userside/cart.html",
        {
            "cart": cart,
            "cart_items": cart_items,
            "total_price": total_price,
        }
    )