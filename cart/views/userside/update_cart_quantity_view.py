from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages

from cart.models import CartItem


MAX_QUANTITY = 5


def update_cart_quantity(request, item_id, action):

    if not request.user.is_authenticated:
        return redirect("login")

    cart_item = get_object_or_404(
        CartItem.objects.select_related(
            "product_variant",
            "product_variant__product",
            "product_variant__product__category"
        ),
        id=item_id,
        cart__user=request.user
    )

    variant = cart_item.product_variant
    product = variant.product
    category = product.category

    if (
        not variant.is_active
        or not product.is_active
        or not category.is_active
        or variant.stock_quantity <= 0
    ):
        messages.error(
            request,
            "This product is currently unavailable."
        )
        return redirect("cart_list")

    if action == "increase":

        if cart_item.quantity >= MAX_QUANTITY:
            messages.error(
                request,
                f"You can add a maximum of {MAX_QUANTITY} items."
            )
            return redirect("cart_list")

        if cart_item.quantity >= variant.stock_quantity:
            messages.error(
                request,
                "You cannot add more than the available stock."
            )
            return redirect("cart_list")

        cart_item.quantity += 1
        cart_item.save()

    elif action == "decrease":

        if cart_item.quantity <= 1:
            cart_item.delete()
            messages.success(
                request,
                "Product removed from cart."
            )
            return redirect("cart_list")

        cart_item.quantity -= 1
        cart_item.save()

    return redirect("cart_list")