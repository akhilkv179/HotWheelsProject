from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import F, Q, Sum
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseNotAllowed

from admin_panel.decorators import admin_required
from products.models import Product, ProductVariant


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Display inventory stock levels and low-stock alerts across products.
@admin_required
def admin_inventory_list(request):

    if request.method != "GET":
        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Only GET requests are allowed."
                },
                status=405
            )
        return HttpResponseNotAllowed(["GET"])

    products = Product.objects.filter(
        is_deleted=False
    ).select_related("category").annotate(
        total_stock=Sum("variants__stock_quantity")
    )

    search = request.GET.get("search", "").strip()
    stock_filter = request.GET.get("stock", "").strip()
    sort = request.GET.get("sort", "newest")

    if search:
        products = products.filter(
            Q(name__icontains=search) |
            Q(category__name__icontains=search)
        )

    if stock_filter == "low":
        products = products.filter(
            total_stock__lte=F("low_stock_threshold")
        )
    elif stock_filter == "out":
        products = products.filter(total_stock__lte=0)
    elif stock_filter == "available":
        products = products.filter(total_stock__gt=0)

    sort_options = {
        "newest": "-created_at",
        "oldest": "created_at",
        "name_az": "name",
        "name_za": "-name",
        "stock_low": "total_stock",
        "stock_high": "-total_stock",
    }

    if sort not in sort_options:
        sort = "newest"

    products = products.order_by(sort_options[sort])

    paginator = Paginator(products, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    if wants_json(request):
        products_data = []

        for product in page_obj:
            products_data.append({
                "id": product.id,
                "name": product.name,
                "category": (
                    product.category.name
                    if product.category
                    else None
                ),
                "total_stock": product.total_stock,
                "low_stock_threshold": product.low_stock_threshold,
                "created_at": product.created_at.isoformat(),
            })

        return JsonResponse(
            {
                "success": True,
                "products": products_data,
                "filters": {
                    "search": search,
                    "stock": stock_filter,
                    "sort": sort,
                },
                "pagination": {
                    "current_page": page_obj.number,
                    "total_pages": paginator.num_pages,
                    "total_products": paginator.count,
                    "has_next": page_obj.has_next(),
                    "has_previous": page_obj.has_previous(),
                    "next_page": (
                        page_obj.next_page_number()
                        if page_obj.has_next()
                        else None
                    ),
                    "previous_page": (
                        page_obj.previous_page_number()
                        if page_obj.has_previous()
                        else None
                    ),
                },
            },
            status=200
        )

    return render(
        request,
        "products/admin_inventory_list.html",
        {
            "products": page_obj,
            "page_obj": page_obj,
            "search": search,
            "selected_stock": stock_filter,
            "selected_sort": sort,
        }
    )


# Display variant-level inventory stock breakdown for a product.
@admin_required
def admin_inventory_detail(request, product_id):

    if request.method != "GET":
        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Only GET requests are allowed."
                },
                status=405
            )
        return HttpResponseNotAllowed(["GET"])

    product = get_object_or_404(
        Product.objects.filter(
            is_deleted=False
        ).prefetch_related("variants"),
        id=product_id
    )

    variants = product.variants.all().order_by("color", "size")

    if wants_json(request):
        variants_data = [
            {
                "id": variant.id,
                "color": variant.color,
                "size": variant.size,
                "stock_quantity": variant.stock_quantity,
            }
            for variant in variants
        ]

        return JsonResponse(
            {
                "success": True,
                "product": {
                    "id": product.id,
                    "name": product.name,
                },
                "variants": variants_data,
                "variant_count": len(variants_data),
            },
            status=200
        )

    return render(
        request,
        "products/admin_inventory_detail.html",
        {
            "product": product,
            "variants": variants,
        }
    )


# Update the inventory stock quantity for a product variant.
@admin_required
def admin_update_stock(request, variant_id):

    if request.method != "POST":
        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Only POST requests are allowed."
                },
                status=405
            )
        return HttpResponseNotAllowed(["POST"])

    variant = get_object_or_404(
        ProductVariant.objects.select_related("product"),
        id=variant_id,
        product__is_deleted=False
    )

    try:
        quantity = int(request.POST.get("stock_quantity", ""))

        if quantity < 0:
            raise ValueError

    except (ValueError, TypeError):
        error_message = (
            "Enter a valid non-negative stock quantity."
        )

        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": error_message,
                },
                status=400
            )

        messages.error(request, error_message)
        return redirect(
            "admin_inventory_detail",
            product_id=variant.product_id
        )

    variant.stock_quantity = quantity
    variant.save(update_fields=["stock_quantity", "updated_at"])

    success_message = "Stock quantity updated successfully."

    if wants_json(request):
        return JsonResponse(
            {
                "success": True,
                "message": success_message,
                "variant": {
                    "id": variant.id,
                    "stock_quantity": variant.stock_quantity,
                },
                "product_id": variant.product_id,
            },
            status=200
        )

    messages.success(request, success_message)

    return redirect(
        "admin_inventory_detail",
        product_id=variant.product_id
    )