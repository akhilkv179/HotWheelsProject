from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required

from wishlist.models import Wishlist, WishlistItem
from products.models import ProductVariant


@login_required
def wishlist_add(request, variant_id):
    variant = get_object_or_404(
        ProductVariant,
        id=variant_id
    )

    wishlist, created = Wishlist.objects.get_or_create(
        user=request.user
    )

    WishlistItem.objects.get_or_create(
        wishlist=wishlist,
        product_variant=variant
    )

    return redirect(request.META.get("HTTP_REFERER", "user_product_list"))