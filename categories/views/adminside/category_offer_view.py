from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse, HttpResponseNotAllowed
from django.urls import reverse
from decimal import Decimal, InvalidOperation

from admin_panel.decorators import admin_required
from categories.models import Category, CategoryOffer


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Return a JSON error or preserve the normal HTML response.
def offer_error(request, message, status=400):
    if wants_json(request):
        return JsonResponse(
            {"success": False, "message": message},
            status=status
        )

    messages.error(request, message)
    return redirect("admin_category_list")


# Create and apply a new promotional discount offer to a category.
@admin_required
def category_offer(request, category_id):

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

    category = get_object_or_404(Category, id=category_id)

    offer_name = request.POST.get("offer_name", "").strip()
    discount_value = request.POST.get("discount_value", "").strip()
    start_date = request.POST.get("start_date", "").strip()
    end_date = request.POST.get("end_date", "").strip()

    if not offer_name:
        return offer_error(request, "Offer name is required.")

    if not discount_value:
        return offer_error(request, "Discount percentage is required.")

    if not start_date:
        return offer_error(request, "Start date is required.")

    if not end_date:
        return offer_error(request, "End date is required.")

    try:
        discount_value = Decimal(discount_value)
    except (InvalidOperation, ValueError):
        return offer_error(request, "Discount must be a valid number.")

    if not discount_value.is_finite():
        return offer_error(request, "Discount must be a valid number.")

    if discount_value <= 0 or discount_value > 100:
        return offer_error(
            request, "Discount must be between 1 and 100."
        )

    try:
        start_date = timezone.datetime.fromisoformat(start_date)
        end_date = timezone.datetime.fromisoformat(end_date)
    except ValueError:
        return offer_error(request, "Invalid date format.")

    if timezone.is_naive(start_date):
        start_date = timezone.make_aware(
            start_date, timezone.get_current_timezone()
        )

    if timezone.is_naive(end_date):
        end_date = timezone.make_aware(
            end_date, timezone.get_current_timezone()
        )

    if end_date <= start_date:
        return offer_error(
            request, "End date must be after start date."
        )

    # Deactivate existing active offers for this category.
    CategoryOffer.objects.filter(
        category=category,
        is_active=True
    ).update(is_active=False)

    offer = CategoryOffer.objects.create(
        category=category,
        offer_name=offer_name,
        discount_value=discount_value,
        start_date=start_date,
        end_date=end_date,
        is_active=True
    )

    success_message = "Category offer added successfully."

    if wants_json(request):
        return JsonResponse(
            {
                "success": True,
                "message": success_message,
                "offer": {
                    "id": offer.id,
                    "offer_name": offer.offer_name,
                    "discount_value": str(offer.discount_value),
                    "start_date": offer.start_date.isoformat(),
                    "end_date": offer.end_date.isoformat(),
                    "is_active": offer.is_active
                },
                "redirect_url": reverse("admin_category_list")
            },
            status=201
        )

    messages.success(request, success_message)
    return redirect("admin_category_list")


# Activate or deactivate a category discount offer.
@admin_required
def toggle_category_offer(request, offer_id):

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

    offer = get_object_or_404(CategoryOffer, id=offer_id)

    offer.is_active = not offer.is_active
    offer.save(update_fields=["is_active"])

    if offer.is_active:
        success_message = "Category offer activated successfully."
    else:
        success_message = "Category offer deactivated successfully."

    if wants_json(request):
        return JsonResponse(
            {
                "success": True,
                "message": success_message,
                "offer_id": offer.id,
                "is_active": offer.is_active,
                "redirect_url": reverse("admin_category_list")
            },
            status=200
        )

    messages.success(request, success_message)
    return redirect("admin_category_list")