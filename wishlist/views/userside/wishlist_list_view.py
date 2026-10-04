from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from wishlist.models import Wishlist


@login_required
def wishlist_list(request):
    wishlist, created = Wishlist.objects.get_or_create(
        user=request.user
    )

    items = wishlist.items.select_related(
        "product_variant",
        "product_variant__product",
        "product_variant__product__category"
    ).prefetch_related(
        "product_variant__images"
    )

    for item in items:
        variant = item.product_variant
        product = variant.product

        if not product.is_active or not product.category.is_active or not variant.is_active:
            item.is_available = False
        elif variant.stock_quantity <= 0:
            item.is_available = False
        else:
            item.is_available = True

    return render(
        request,
        "userside/wishlist.html",
        {
            "wishlist": wishlist,
            "items": items,
        }
    )