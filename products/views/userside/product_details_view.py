from django.shortcuts import render, redirect
from django.utils import timezone
from django.db.models import Avg, Count
from decimal import Decimal, ROUND_HALF_UP

from products.models import Product
from reviews.models import Review
from wishlist.models import WishlistItem


def product_details(request, product_id):
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

    # Redirect only when the product does not exist.
    if not product:
        return redirect("user_product_list")

    # Check whether the product and its category are listed.
    category_is_active = (
        product.category.is_active
        if product.category_id
        else False
    )

    # Keep the details page accessible, but mark unavailable products.
    variants = list(
        product.variants.filter(
            is_active=True
        ).prefetch_related("images")
    )

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

    # Calculate stock across the active variants.
    total_stock = sum(
        variant.stock_quantity
        for variant in variants
    )

    if product_unavailable:
        stock_status = "unavailable"
    elif total_stock == 0:
        stock_status = "sold_out"
    elif total_stock <= product.low_stock_threshold:
        stock_status = "low_stock"
    else:
        stock_status = "in_stock"

    # Determine the stock status of each variant.
    for variant in variants:
        if variant.stock_quantity <= 0:
            variant.stock_status = "out_of_stock"
        elif variant.stock_quantity <= product.low_stock_threshold:
            variant.stock_status = "low_stock"
        else:
            variant.stock_status = "in_stock"

    # Attach wishlist information for logged-in users.
    if request.user.is_authenticated:
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
    else:
        for variant in variants:
            variant.wishlist_item_id = None

    # Collect images from the active variants.
    images = []

    for variant in variants:
        for image in variant.images.all():
            images.append(image)

    # Recommend other active products in the same category.
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

    # Retrieve reviews and calculate the average rating.
    reviews = Review.objects.filter(
        order_item__product_variant__product=product
    ).select_related(
        "order_item",
        "order_item__order",
        "order_item__order__user",
    ).order_by("-created_at")

    rating_data = reviews.aggregate(
        average_rating=Avg("rating"),
        total_reviews=Count("id"),
    )

    average_rating = rating_data["average_rating"]
    total_reviews = rating_data["total_reviews"]

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
    )