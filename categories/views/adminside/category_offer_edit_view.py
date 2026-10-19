from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse, HttpResponseNotAllowed
from django.urls import reverse
from decimal import Decimal, InvalidOperation

from admin_panel.decorators import admin_required
from categories.models import CategoryOffer


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Edit and update an existing promotional discount offer for a category.
@admin_required
def category_offer_edit(request, offer_id):

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

    offer_name = request.POST.get("offer_name", "").strip()
    discount_value = request.POST.get("discount_value", "").strip()
    start_date = request.POST.get("start_date", "").strip()
    end_date = request.POST.get("end_date", "").strip()

    # Helper to return JSON errors or preserve HTML messages and redirects.
    def validation_error(message, status=400):
        if wants_json(request):
            return JsonResponse(
                {"success": False, "message": message},
                status=status
            )

        messages.error(request, message)
        return redirect("admin_category_list")

    if not offer_name:
        return validation_error("Offer name is required.")

    if not discount_value:
        return validation_error("Discount percentage is required.")

    if not start_date:
        return validation_error("Start date is required.")

    if not end_date:
        return validation_error("End date is required.")

    try:
        discount_value = Decimal(discount_value)
    except (InvalidOperation, ValueError):
        return validation_error("Discount must be a valid number.")

    if not discount_value.is_finite():
        return validation_error("Discount must be a valid number.")

    if discount_value <= 0 or discount_value > 100:
        return validation_error("Discount must be between 1 and 100.")

    try:
        start_date = timezone.datetime.fromisoformat(start_date)
        end_date = timezone.datetime.fromisoformat(end_date)
    except ValueError:
        return validation_error("Invalid date format.")

    # Make dates timezone-aware when timezone support is enabled.
    if timezone.is_naive(start_date):
        start_date = timezone.make_aware(
            start_date, timezone.get_current_timezone()
        )

    if timezone.is_naive(end_date):
        end_date = timezone.make_aware(
            end_date, timezone.get_current_timezone()
        )

    if end_date <= start_date:
        return validation_error("End date must be after start date.")

    offer.offer_name = offer_name
    offer.discount_value = discount_value
    offer.start_date = start_date
    offer.end_date = end_date
    offer.save()

    success_message = "Category offer updated successfully."

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
                },
                "redirect_url": reverse("admin_category_list")
            },
            status=200
        )

    messages.success(request, success_message)
    return redirect("admin_category_list")