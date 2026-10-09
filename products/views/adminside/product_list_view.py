from django.shortcuts import render, redirect,get_object_or_404
from admin_panel.decorators import admin_required
from products.models import Product
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator
from django.contrib import messages



def product_list(request):

    if request.method == "POST":

        product_id = request.POST.get("product_id")

        product = Product.objects.get(id=product_id)

        product.is_active = not product.is_active
        product.save()

        if product.is_active:
            messages.success(request, "Product listed successfully.")
        else:
            messages.success(request, "Product unlisted successfully.")

        return redirect("admin_product_list")

    search_query = request.GET.get("search", "").strip()
    sort = request.GET.get("sort", "newest")

    products = Product.objects.all()

    

    if search_query:
        products = products.filter(
            Q(name__icontains=search_query)
            | Q(category__name__icontains=search_query)
        )

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

    paginator = Paginator(products,5)

    page_number = request.GET.get("page")

    page_obj = paginator.get_page(page_number)

    current_time = timezone.now()

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

    return render(
        request,
        "adminside/product_list.html",
        {
            "page_obj": page_obj,
            "search_query": search_query,
            "sort": sort,
        }
    )





def product_variant(request,product_id):
    product = get_object_or_404 (Product,id = product_id)

    variants = product.variants.all()

    return render(request,"adminside/product_list.html",{"variants": variants,})
