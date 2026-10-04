from django.shortcuts import render
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

from products.models import Product
from categories.models import Category
from wishlist.models import WishlistItem


def product_list(request):
    search_query = request.GET.get("search", "").strip()
    sort = request.GET.get("sort", "newest")
    category_id = request.GET.get("category", "").strip()
    min_price = request.GET.get("min_price", "").strip()
    max_price = request.GET.get("max_price", "").strip()

    products = Product.objects.filter(
        is_active=True,
        category__is_active=True,
        variants__is_active=True
    ).select_related(
        "category"
    ).prefetch_related(
        "variants__images",
        "offers"
    ).distinct()

    categories = Category.objects.filter(
        is_active=True
    ).order_by("name")

    if search_query:
        products = products.filter(
            Q(name__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(category__name__icontains=search_query)
        )

    if category_id:
        products = products.filter(
            category_id=category_id
        )

    current_time = timezone.now()

    for product in products:
        offer = product.offers.filter(
            is_active=True,
            start_date__lte=current_time,
            end_date__gte=current_time
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
                rounding=ROUND_HALF_UP
            )

            product.sale_price = sale_price
            product.offer_percentage = offer.discount_value
            product.offer_name = offer.offer_name

        else:
            product.sale_price = product.regular_price
            product.offer_percentage = None
            product.offer_name = None

    if min_price:
        try:
            min_price_value = Decimal(min_price)

            products = [
                product
                for product in products
                if product.sale_price >= min_price_value
            ]

        except InvalidOperation:
            pass

    if max_price:
        try:
            max_price_value = Decimal(max_price)

            products = [
                product
                for product in products
                if product.sale_price <= max_price_value
            ]

        except InvalidOperation:
            pass

    if sort == "price_low":
        products = sorted(
            products,
            key=lambda product: product.sale_price
        )

    elif sort == "price_high":
        products = sorted(
            products,
            key=lambda product: product.sale_price,
            reverse=True
        )

    elif sort == "name_az":
        products = sorted(
            products,
            key=lambda product: product.name.lower()
        )

    elif sort == "name_za":
        products = sorted(
            products,
            key=lambda product: product.name.lower(),
            reverse=True
        )

    else:
        products = sorted(
            products,
            key=lambda product: product.created_at,
            reverse=True
        )

    paginator = Paginator(products, 12)

    page_number = request.GET.get("page")

    page_obj = paginator.get_page(page_number)

    wishlist_items = {}

    if request.user.is_authenticated:
        wishlist_items = {
            item.product_variant_id: item.id
            for item in WishlistItem.objects.filter(
                wishlist__user=request.user
            )
        }

    for product in page_obj:
        for variant in product.variants.all():
            variant.wishlist_item_id = wishlist_items.get(
                variant.id
            )

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
        }
    )