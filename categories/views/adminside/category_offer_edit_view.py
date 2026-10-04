from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from decimal import Decimal, InvalidOperation

from admin_panel.decorators import admin_required
from categories.models import CategoryOffer


@admin_required
def category_offer_edit(request, offer_id):
    offer = get_object_or_404(CategoryOffer, id=offer_id)

    if request.method == "POST":
        offer_name = request.POST.get("offer_name", "").strip()
        discount_value = request.POST.get("discount_value", "").strip()
        start_date = request.POST.get("start_date", "").strip()
        end_date = request.POST.get("end_date", "").strip()

        if not offer_name:
            messages.error(request, "Offer name is required.")
            return redirect("admin_category_list")

        if not discount_value:
            messages.error(request, "Discount percentage is required.")
            return redirect("admin_category_list")

        if not start_date:
            messages.error(request, "Start date is required.")
            return redirect("admin_category_list")

        if not end_date:
            messages.error(request, "End date is required.")
            return redirect("admin_category_list")

        try:
            discount_value = Decimal(discount_value)
        except InvalidOperation:
            messages.error(request, "Discount must be a valid number.")
            return redirect("admin_category_list")

        if discount_value <= 0 or discount_value > 100:
            messages.error(request, "Discount must be between 1 and 100.")
            return redirect("admin_category_list")

        try:
            start_date = timezone.datetime.fromisoformat(start_date)
            end_date = timezone.datetime.fromisoformat(end_date)
        except ValueError:
            messages.error(request, "Invalid date format.")
            return redirect("admin_category_list")

        if end_date <= start_date:
            messages.error(request, "End date must be after start date.")
            return redirect("admin_category_list")

        offer.offer_name = offer_name
        offer.discount_value = discount_value
        offer.start_date = start_date
        offer.end_date = end_date
        offer.save()

        messages.success(request, "Category offer updated successfully.")
        return redirect("admin_category_list")

    return redirect("admin_category_list")