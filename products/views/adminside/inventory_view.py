from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import F, Q, Sum
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from products.models import Product, ProductVariant


def admin_inventory_list(request):
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

    products = products.order_by(sort_options.get(sort, "-created_at"))

    paginator = Paginator(products, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "products/admin_inventory_list.html", {
        "products": page_obj,
        "page_obj": page_obj,
        "search": search,
        "selected_stock": stock_filter,
        "selected_sort": sort,
    })


def admin_inventory_detail(request, product_id):
    product = get_object_or_404(
        Product.objects.filter(is_deleted=False).prefetch_related("variants"),
        id=product_id
    )

    variants = product.variants.all().order_by("color", "size")

    return render(request, "products/admin_inventory_detail.html", {
        "product": product,
        "variants": variants,
    })


@require_POST
def admin_update_stock(request, variant_id):
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
        messages.error(request, "Enter a valid non-negative stock quantity.")
        return redirect("admin_inventory_detail", product_id=variant.product_id)

    variant.stock_quantity = quantity
    variant.save(update_fields=["stock_quantity", "updated_at"])

    messages.success(request, "Stock quantity updated successfully.")

    return redirect("admin_inventory_detail", product_id=variant.product_id)