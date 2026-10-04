from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages

from cart.models import CartItem


def remove_from_cart(request, item_id):

    if not request.user.is_authenticated:
        return redirect("login")

    cart_item = get_object_or_404(
        CartItem,
        id=item_id,
        cart__user=request.user
    )

    cart_item.delete()

    messages.success(request, "Product removed from cart.")

    return redirect("user_product_list")