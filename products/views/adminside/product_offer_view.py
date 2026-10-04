from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from decimal import Decimal, InvalidOperation
from django.utils import timezone

from admin_panel.decorators import admin_required
from products.models import Product, ProductOffer



def product_offer(request, product_id):

    product = get_object_or_404(Product, id=product_id)

    if request.method == "POST":

        offer_name = request.POST.get("offer_name", "").strip()
        discount_value = request.POST.get("discount_value", "").strip()
        start_date = request.POST.get("start_date", "").strip()
        end_date = request.POST.get("end_date", "").strip()

        if not offer_name:
            messages.error(request, "Offer name is required.")
            return redirect("admin_product_list")

        if not discount_value:
            messages.error(request, "Discount percentage is required.")
            return redirect("admin_product_list")

        if not start_date:
            messages.error(request, "Start date is required.")
            return redirect("admin_product_list")

        if not end_date:
            messages.error(request, "End date is required.")
            return redirect("admin_product_list")

        try:
            discount_value = Decimal(discount_value)
        except InvalidOperation:
            messages.error(request, "Discount must be a valid number.")
            return redirect("admin_product_list")

        if discount_value <= 0 or discount_value > 100:
            messages.error(request, "Discount must be between 1 and 100.")
            return redirect("admin_product_list")

        try:
            start_date = timezone.datetime.fromisoformat(start_date)
            end_date = timezone.datetime.fromisoformat(end_date)
        except ValueError:
            messages.error(request, "Invalid date format.")
            return redirect("admin_product_list")

        if end_date <= start_date:
            messages.error(request, "End date must be after start date.")
            return redirect("admin_product_list")

        ProductOffer.objects.filter(
            product=product,
            is_active=True
        ).update(is_active=False)

        ProductOffer.objects.create(
            product=product,
            offer_name=offer_name,
            discount_value=discount_value,
            start_date=start_date,
            end_date=end_date,
            is_active=True
        )

        messages.success(request, "Product offer added successfully.")

        return redirect("admin_product_list")

    return redirect("admin_product_list")


def toggle_product_offer(request, offer_id):

    offer = get_object_or_404(ProductOffer, id=offer_id)

    offer.is_active = not offer.is_active
    offer.save()

    if offer.is_active:
        messages.success(request, "Product offer activated successfully.")
    else:
        messages.success(request, "Product offer deactivated successfully.")

    return redirect("admin_product_list")