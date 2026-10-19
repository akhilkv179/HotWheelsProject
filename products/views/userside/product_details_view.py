
from django.shortcuts import render, redirect
from django.utils import timezone
from django.db.models import Avg, Count
from django.http import JsonResponse
from decimal import Decimal, ROUND_HALF_UP
from django.contrib.auth.decorators import login_required
from products.models import Product
from reviews.models import Review
from wishlist.models import WishlistItem


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Display product details, variants, offers, and reviews for customers.
@login_required
def product_details(request, product_id):
    # Allow only GET requests for viewing product details.
    if request.method != "GET":
        if wants_json(request):
            return JsonResponse(
                {"error": "Method not allowed."},
                status=405,
            )
        return redirect("user_product_list")

    # Find the product even if it has been unlisted.
    product = (
        Product.objects
        .filter(id=product_id)
        .select_related("category")
        .prefetch_related(
            "variants__images",
            "offers",
        )
        .first()
    )

    # Return an error if the requested product does not exist.
    if not product:
        if wants_json(request):
            return JsonResponse(
                {"error": "Product not found."},
                status=404,
            )
        return redirect("user_product_list")

    # Check whether the product and its category are listed.
    category_is_active = (
        product.category.is_active
        if product.category_id
        else False
    )

    # Get active variants to display on the product details page.
    variants = list(
        product.variants.filter(
            is_active=True
        ).prefetch_related("images")
    )

    # Determine whether the product is unavailable for purchase.
    product_unavailable = (
        not product.is_active
        or not category_is_active
        or not variants
    )

    unavailable_message = (
        "Product Unavailable"
        if product_unavailable
        else ""
    )

    current_time = timezone.now()

    # Find the currently active product offer.
    offer = product.offers.filter(
        is_active=True,
        start_date__lte=current_time,
        end_date__gte=current_time,
    ).order_by("-discount_value").first()

    # Calculate the sale price when an active offer exists.
    if offer:
        discount_amount = (
            product.regular_price
            * offer.discount_value
            / Decimal("100")
        )

        sale_price = (
            product.regular_price - discount_amount
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        product.sale_price = sale_price
        product.offer_percentage = offer.discount_value
        product.offer_name = offer.offer_name

    else:
        product.sale_price = product.regular_price
        product.offer_percentage = None
        product.offer_name = None

    # Calculate the combined stock of all active variants.
    total_stock = sum(
        variant.stock_quantity
        for variant in variants
    )

    # Determine the overall stock status of the product.
    if product_unavailable:
        stock_status = "unavailable"
    elif total_stock == 0:
        stock_status = "sold_out"
    elif total_stock <= product.low_stock_threshold:
        stock_status = "low_stock"
    else:
        stock_status = "in_stock"

    # Determine the stock status of each active variant.
    for variant in variants:
        if variant.stock_quantity <= 0:
            variant.stock_status = "out_of_stock"
        elif variant.stock_quantity <= product.low_stock_threshold:
            variant.stock_status = "low_stock"
        else:
            variant.stock_status = "in_stock"

    # Attach wishlist item IDs to each variant for the current user.
    wishlist_items = {
        item.product_variant_id: item.id
        for item in WishlistItem.objects.filter(
            wishlist__user=request.user,
            product_variant__product=product,
        )
    }

    for variant in variants:
        variant.wishlist_item_id = wishlist_items.get(
            variant.id
        )

    # Collect images belonging to the active variants.
    images = []

    for variant in variants:
        for image in variant.images.all():
            images.append(image)

    # Find other active products in the same category.
    related_products = Product.objects.filter(
        is_active=True,
        category__is_active=True,
        variants__is_active=True,
        category=product.category,
    ).exclude(
        id=product.id
    ).select_related(
        "category"
    ).prefetch_related(
        "variants__images",
        "offers",
    ).distinct()[:4]

    # Build breadcrumb information for the product page.
    breadcrumbs = [
        {
            "name": "Products",
            "url": "/p/products/",
        },
        {
            "name": (
                product.category.name
                if product.category_id
                else "Category"
            ),
            "url": (
                f"/p/products/?category={product.category_id}"
                if product.category_id
                else None
            ),
        },
        {
            "name": product.name,
            "url": None,
        },
    ]

    # Retrieve product reviews, newest first.
    reviews = Review.objects.filter(
        order_item__product_variant__product=product
    ).select_related(
        "order_item",
        "order_item__order",
        "order_item__order__user",
    ).order_by("-created_at")

    # Calculate the average rating and total number of reviews.
    rating_data = reviews.aggregate(
        average_rating=Avg("rating"),
        total_reviews=Count("id"),
    )

    average_rating = rating_data["average_rating"]
    total_reviews = rating_data["total_reviews"]

    # Return product details as JSON when requested by the client.
    if wants_json(request):
        return JsonResponse(
            {
                "product": {
                    "id": product.id,
                    "name": product.name,
                    "regular_price": str(product.regular_price),
                    "sale_price": str(product.sale_price),
                    "offer_percentage": (
                        str(product.offer_percentage)
                        if product.offer_percentage is not None
                        else None
                    ),
                    "offer_name": product.offer_name,
                    "is_active": product.is_active,
                    "category_is_active": category_is_active,
                    "product_unavailable": product_unavailable,
                    "unavailable_message": unavailable_message,
                    "total_stock": total_stock,
                    "stock_status": stock_status,
                    "can_purchase": (
                        not product_unavailable and total_stock > 0
                    ),
                },
                "variants": [
                    {
                        "id": variant.id,
                        "color": variant.color,
                        "size": variant.size,
                        "price": str(variant.price),
                        "stock_quantity": variant.stock_quantity,
                        "stock_status": variant.stock_status,
                        "wishlist_item_id": variant.wishlist_item_id,
                    }
                    for variant in variants
                ],
                "breadcrumbs": breadcrumbs,
                "related_products": [
                    {
                        "id": related.id,
                        "name": related.name,
                        "regular_price": str(related.regular_price),
                    }
                    for related in related_products
                ],
                "reviews": [
                    {
                        "id": review.id,
                        "rating": review.rating,
                        "created_at": review.created_at.isoformat(),
                    }
                    for review in reviews
                ],
                "average_rating": (
                    float(average_rating)
                    if average_rating is not None
                    else None
                ),
                "total_reviews": total_reviews,
            },
            status=200,
        )

    # Render the normal HTML product details page.
    return render(
        request,
        "userside/product_details.html",
        {
            "product": product,
            "variants": variants,
            "images": images,
            "total_stock": total_stock,
            "stock_status": stock_status,
            "product_unavailable": product_unavailable,
            "unavailable_message": unavailable_message,
            "can_purchase": (
                not product_unavailable and total_stock > 0
            ),
            "breadcrumbs": breadcrumbs,
            "related_products": related_products,
            "reviews": reviews,
            "average_rating": average_rating,
            "total_reviews": total_reviews,
        },
        status=200,
    )
