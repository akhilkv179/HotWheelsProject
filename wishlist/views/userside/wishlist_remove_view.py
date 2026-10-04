from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required

from wishlist.models import WishlistItem


@login_required
def wishlist_remove(request, item_id):
    item = get_object_or_404(
        WishlistItem,
        id=item_id,
        wishlist__user=request.user
    )

    item.delete()

    return redirect("wishlist")