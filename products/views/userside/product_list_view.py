
from django.shortcuts import render
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils import timezone
from django.http import JsonResponse
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from django.contrib.auth.decorators import login_required
from products.models import Product
from categories.models import Category
from wishlist.models import WishlistItem


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Display the customer product catalog with search, filtering, and sorting.
@login_required
def product_list(request):
    # Allow only GET requests to retrieve the product catalog.
    if request.method != "GET":
        return JsonResponse(
            {"error": "Method not allowed."},
            status=405,
        )

    # Read search, sorting, category, and price filter values.
    search_query = request.GET.get("search", "").strip()
    sort = request.GET.get("sort", "newest")
    category_id = request.GET.get("category", "").strip()
    min_price = request.GET.get("min_price", "").strip()
    max_price = request.GET.get("max_price", "").strip()

    # Retrieve products that are not deleted and belong to active categories.
    products = Product.objects.filter(
        is_deleted=False,
        category__is_active=True,
        category__is_deleted=False,
        variants__is_active=True,
    ).select_related(
        "category"
    ).prefetch_related(
        "variants__images",
        "offers",
    ).distinct()

    # Retrieve active categories for the catalog filter.
    categories = Category.objects.filter(
        is_active=True
    ).order_by("name")

    # Search products by name, description, or category name.
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(category__name__icontains=search_query)
        )

    # Filter products by the selected category.
    if category_id:
        products = products.filter(
            category_id=category_id
        )

    current_time = timezone.now()

    # Calculate the sale price using the best currently active offer.
    for product in products:
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

    # Filter products by the minimum sale price.
    if min_price:
        try:
            min_price_value = Decimal(min_price)

            if (
                not min_price_value.is_finite()
                or min_price_value < 0
            ):
                raise InvalidOperation

            products = [
                product for product in products
                if product.sale_price >= min_price_value
            ]

        except InvalidOperation:
            if wants_json(request):
                return JsonResponse(
                    {"error": "Enter a valid minimum price."},
                    status=400,
                )

    # Filter products by the maximum sale price.
    if max_price:
        try:
            max_price_value = Decimal(max_price)

            if (
                not max_price_value.is_finite()
                or max_price_value < 0
            ):
                raise InvalidOperation

            products = [
                product for product in products
                if product.sale_price <= max_price_value
            ]

        except InvalidOperation:
            if wants_json(request):
                return JsonResponse(
                    {"error": "Enter a valid maximum price."},
                    status=400,
                )

    # Sort products according to the selected option.
    if sort == "price_low":
        products = sorted(
            products,
            key=lambda product: product.sale_price,
        )

    elif sort == "price_high":
        products = sorted(
            products,
            key=lambda product: product.sale_price,
            reverse=True,
        )

    elif sort == "name_az":
        products = sorted(
            products,
            key=lambda product: product.name.lower(),
        )

    elif sort == "name_za":
        products = sorted(
            products,
            key=lambda product: product.name.lower(),
            reverse=True,
        )

    else:
        products = sorted(
            products,
            key=lambda product: product.created_at,
            reverse=True,
        )

    # Split the filtered products into pages containing 12 products.
    paginator = Paginator(products, 12)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Retrieve wishlist item IDs belonging to the current user.
    wishlist_items = {
        item.product_variant_id: item.id
        for item in WishlistItem.objects.filter(
            wishlist__user=request.user
        )
    }

    # Attach wishlist information to each displayed product variant.
    for product in page_obj:
        for variant in product.variants.all():
            variant.wishlist_item_id = wishlist_items.get(
                variant.id
            )

    # Return product catalog data as JSON when requested.
    if wants_json(request):
        return JsonResponse(
            {
                "products": [
                    {
                        "id": product.id,
                        "name": product.name,
                        "description": product.description,
                        "category": (
                            product.category.name
                            if product.category_id
                            else None
                        ),
                        "regular_price": str(product.regular_price),
                        "sale_price": str(product.sale_price),
                        "offer_percentage": (
                            str(product.offer_percentage)
                            if product.offer_percentage is not None
                            else None
                        ),
                        "offer_name": product.offer_name,
                        "variants": [
                            {
                                "id": variant.id,
                                "color": variant.color,
                                "size": variant.size,
                                "price": str(variant.price),
                                "stock_quantity": variant.stock_quantity,
                                "wishlist_item_id": variant.wishlist_item_id,
                            }
                            for variant in product.variants.filter(
                                is_active=True
                            )
                        ],
                    }
                    for product in page_obj
                ],
                "pagination": {
                    "current_page": page_obj.number,
                    "total_pages": paginator.num_pages,
                    "total_products": paginator.count,
                    "has_next": page_obj.has_next(),
                    "has_previous": page_obj.has_previous(),
                },
                "filters": {
                    "search": search_query,
                    "sort": sort,
                    "category": category_id,
                    "min_price": min_price,
                    "max_price": max_price,
                },
                "categories": [
                    {
                        "id": category.id,
                        "name": category.name,
                    }
                    for category in categories
                ],
            },
            status=200,
        )

    # Render the normal HTML product catalog for browser requests.
    return render(
        request,
        "userside/product_list.html",
        {
            "page_obj": page_obj,
            "categories": categories,
            "search_query": search_query,
            "sort": sort,
            "selected_category": category_id,
            "min_price": min_price,
            "max_price": max_price,
            "wishlist_items": wishlist_items,
        },
        status=200,
    )
