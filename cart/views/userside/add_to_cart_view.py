from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages

from cart.models import Cart, CartItem
from products.models import ProductVariant
from wishlist.models import WishlistItem


def add_to_cart(request, variant_id):


    variant = get_object_or_404(ProductVariant.objects.select_related("product","product__category"),id=variant_id)

    if not variant.is_active:
        messages.error(request, "This product variant is unavailable.")
        return redirect("user_product_list")

    if not variant.product.is_active:
        messages.error(request, "This product is unavailable.")
        return redirect("user_product_list")

    if not variant.product.category.is_active:
        messages.error(request, "This product is unavailable.")
        return redirect("user_product_list")

    if variant.stock_quantity <= 0:
        messages.error(request, "This product is out of stock.")
        return redirect("user_product_details",product_id=variant.product.id)

    cart, created = Cart.objects.get_or_create(
        user=request.user
    )

    cart_item = CartItem.objects.filter(
        cart=cart,
        product_variant=variant
    ).first()

    MAX_QUANTITY = 5

    if cart_item:
        new_quantity = cart_item.quantity + 1

        if new_quantity > MAX_QUANTITY:
            messages.error(request,f"You can add a maximum of {MAX_QUANTITY} items.")
            return redirect("user_product_details",product_id=variant.product.id)

        if new_quantity > variant.stock_quantity:
            messages.error(request,"You cannot add more than the available stock.")
            return redirect("user_product_details",product_id=variant.product.id)

        cart_item.quantity = new_quantity
        cart_item.save()

    else:

        CartItem.objects.create(
            cart=cart,
            product_variant=variant,
            quantity=1,
            unit_price=variant.price
        )

    WishlistItem.objects.filter(
        wishlist__user=request.user,
        product_variant=variant
    ).delete()

    messages.success(request, "Product added to cart.")

    return redirect("user_product_details",product_id=variant.product.id)