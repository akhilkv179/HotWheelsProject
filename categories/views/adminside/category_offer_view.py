from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponseNotAllowed
from decimal import Decimal, InvalidOperation

from admin_panel.decorators import admin_required
from categories.models import Category, CategoryOffer


def category_offer(request, category_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    category = get_object_or_404(Category, id=category_id)

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

    CategoryOffer.objects.filter(
        category=category,
        is_active=True
    ).update(is_active=False)

    CategoryOffer.objects.create(
        category=category,
        offer_name=offer_name,
        discount_value=discount_value,
        start_date=start_date,
        end_date=end_date,
        is_active=True
    )

    messages.success(request, "Category offer added successfully.")
    return redirect("admin_category_list")


def toggle_category_offer(request, offer_id):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    offer = get_object_or_404(CategoryOffer, id=offer_id)

    offer.is_active = not offer.is_active
    offer.save()

    if offer.is_active:
        messages.success(request, "Category offer activated successfully.")
    else:
        messages.success(request, "Category offer deactivated successfully.")

    return redirect("admin_category_list")