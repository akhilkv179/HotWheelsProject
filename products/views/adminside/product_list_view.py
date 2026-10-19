
from decimal import Decimal, ROUND_HALF_UP

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse, HttpResponseNotAllowed, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone

from admin_panel.decorators import admin_required
from products.models import Product


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Display a searchable and paginated catalog of all products for administrators.
@admin_required
def product_list(request):

    # Allow GET requests for listing products and POST requests for listing changes.
    if request.method not in ["GET", "POST"]:
        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Only GET and POST requests are allowed.",
                },
                status=405
            )

        return HttpResponseNotAllowed(["GET", "POST"])

    # Handle listing or unlisting a product.
    if request.method == "POST":

        product_id = request.POST.get("product_id", "").strip()

        if not product_id:
            if wants_json(request):
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Product ID is required.",
                    },
                    status=400
                )

            messages.error(request, "Product ID is required.")
            return redirect("admin_product_list")

        try:
            product = Product.objects.get(id=product_id)
        except (Product.DoesNotExist, ValueError, TypeError):
            if wants_json(request):
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Product not found.",
                    },
                    status=404
                )

            messages.error(request, "Product not found.")
            return redirect("admin_product_list")

        # Toggle the product's active status.
        product.is_active = not product.is_active
        product.save(update_fields=["is_active"])

        if product.is_active:
            success_message = "Product listed successfully."
        else:
            success_message = "Product unlisted successfully."

        # Return the result to JSON clients.
        if wants_json(request):
            return JsonResponse(
                {
                    "success": True,
                    "message": success_message,
                    "product_id": product.id,
                    "is_active": product.is_active,
                    "redirect_url": reverse("admin_product_list"),
                },
                status=200
            )

        messages.success(request, success_message)
        return redirect("admin_product_list")

    # Read the search term and sorting option from the URL.
    search_query = request.GET.get("search", "").strip()
    sort = request.GET.get("sort", "newest")

    products = Product.objects.all()

    # Filter products by product name or category name.
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query)
            | Q(category__name__icontains=search_query)
        )

    # Apply the selected sorting order.
    if sort == "price_low":
        products = products.order_by("regular_price")
    elif sort == "price_high":
        products = products.order_by("-regular_price")
    elif sort == "name_az":
        products = products.order_by("name")
    elif sort == "name_za":
        products = products.order_by("-name")
    else:
        products = products.order_by("-created_at")

    # Display five products per page.
    paginator = Paginator(products, 5)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    current_time = timezone.now()
    product_results = []

    # Calculate the current sale price for each product on this page.
    for product in page_obj:

        offer = product.offers.filter(
            is_active=True,
            start_date__lte=current_time,
            end_date__gte=current_time,
        ).order_by("-discount_value").first()

        if offer:
            discount = offer.discount_value

            discount_amount = (
                product.regular_price * discount / Decimal("100")
            )

            sale_price = (
                product.regular_price - discount_amount
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )

            product.sale_price = sale_price
            product.offer_percentage = discount
            product.offer_name = offer.offer_name

        else:
            product.sale_price = product.regular_price
            product.offer_percentage = None
            product.offer_name = None

        # Prepare JSON-safe product details.
        product_results.append({
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
            "category_id": product.category_id,
            "category_name": (
                product.category.name
                if product.category
                else None
            ),
            "is_active": product.is_active,
        })

    # Return product data and pagination details to JSON clients.
    if wants_json(request):
        return JsonResponse(
            {
                "success": True,
                "products": product_results,
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
                "search_query": search_query,
                "sort": sort,
            },
            status=200
        )

    # Preserve the original HTML product listing.
    return render(
        request,
        "adminside/product_list.html",
        {
            "page_obj": page_obj,
            "search_query": search_query,
            "sort": sort,
        }
    )


# Display variants and specifications for a selected product.
@admin_required
def product_variant(request, product_id):

    # This view displays data, so only GET requests are accepted.
    if request.method != "GET":
        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Only GET requests are allowed.",
                },
                status=405
            )

        return HttpResponseNotAllowed(["GET"])

    # Find the selected product.
    try:
        product = get_object_or_404(Product, id=product_id)
    except Http404:
        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Product not found.",
                },
                status=404
            )
        raise

    variants = product.variants.all()

    # Return product variants as JSON when requested.
    if wants_json(request):
        return JsonResponse(
            {
                "success": True,
                "product_id": product.id,
                "product_name": product.name,
                "variants": [
                    {
                        "id": variant.id,
                        "color": variant.color,
                        "size": variant.size,
                        "price": str(variant.price),
                        "stock_quantity": variant.stock_quantity,
                    }
                    for variant in variants
                ],
            },
            status=200
        )

    # Preserve the existing HTML template and context.
    return render(
        request,
        "adminside/product_list.html",
        {
            "variants": variants,
        }
    )
