
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from wishlist.models import Wishlist, WishlistItem
from products.models import ProductVariant


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Toggle adding or removing a product variant in the user's wishlist.
@login_required
def wishlist_add(request, variant_id):
    # Allow wishlist changes only through POST requests.
    if request.method != "POST":
        if wants_json(request):
            return JsonResponse(
                {"error": "Method not allowed."},
                status=405,
            )
        return redirect(
            request.META.get("HTTP_REFERER", "user_product_list")
        )

    # Find the requested product variant.
    variant = get_object_or_404(
        ProductVariant,
        id=variant_id,
    )

    # Get the user's wishlist or create one if it does not exist.
    wishlist, created = Wishlist.objects.get_or_create(
        user=request.user
    )

    # Check whether this variant is already in the wishlist.
    wishlist_item = WishlistItem.objects.filter(
        wishlist=wishlist,
        product_variant=variant,
    ).first()

    # Remove the variant if it already exists in the wishlist.
    if wishlist_item:
        wishlist_item.delete()
        action = "removed"
        status_code = 200

    # Add the variant if it is not already in the wishlist.
    else:
        wishlist_item = WishlistItem.objects.create(
            wishlist=wishlist,
            product_variant=variant,
        )
        action = "added"
        status_code = 201

    # Return the result as JSON when requested by the client.
    if wants_json(request):
        return JsonResponse(
            {
                "message": f"Product variant {action} to wishlist.",
                "action": action,
                "variant_id": variant.id,
                "wishlist_item_id": (
                    wishlist_item.id if action == "added" else None
                ),
            },
            status=status_code,
        )

    # Redirect browser requests back to the previous page.
    return redirect(
        request.META.get("HTTP_REFERER", "user_product_list")
    )
