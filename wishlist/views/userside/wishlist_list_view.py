
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from wishlist.models import Wishlist


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Display wishlist items with their current availability status.
@login_required
def wishlist_list(request):
    # Allow only GET requests to view wishlist items.
    if request.method != "GET":
        if wants_json(request):
            return JsonResponse(
                {"error": "Method not allowed."},
                status=405,
            )
        return render(
            request,
            "userside/wishlist.html",
            {"wishlist": None, "items": []},
            status=405,
        )

    # Get the user's wishlist or create one if it does not exist.
    wishlist, created = Wishlist.objects.get_or_create(
        user=request.user
    )

    # Retrieve wishlist items with related product and image data.
    items = wishlist.items.select_related(
        "product_variant",
        "product_variant__product",
        "product_variant__product__category",
    ).prefetch_related(
        "product_variant__images"
    )

    # Determine whether each wishlist item is available for purchase.
    for item in items:
        variant = item.product_variant
        product = variant.product

        # Mark items unavailable when the product, category, or variant is inactive.
        if (
            not product.is_active
            or not product.category
            or not product.category.is_active
            or not variant.is_active
        ):
            item.is_available = False

        # Mark items unavailable when there is no stock.
        elif variant.stock_quantity <= 0:
            item.is_available = False

        else:
            item.is_available = True

    # Return wishlist data as JSON when requested by the client.
    if wants_json(request):
        return JsonResponse(
            {
                "wishlist_id": wishlist.id,
                "items": [
                    {
                        "wishlist_item_id": item.id,
                        "variant_id": item.product_variant.id,
                        "product_id": item.product_variant.product.id,
                        "product_name": item.product_variant.product.name,
                        "color": item.product_variant.color,
                        "size": item.product_variant.size,
                        "price": str(item.product_variant.price),
                        "stock_quantity": item.product_variant.stock_quantity,
                        "is_available": item.is_available,
                    }
                    for item in items
                ],
                "total_items": len(items),
            },
            status=200,
        )

    # Render the normal HTML wishlist page.
    return render(
        request,
        "userside/wishlist.html",
        {
            "wishlist": wishlist,
            "items": items,
        },
        status=200,
    )
