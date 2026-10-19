
from decimal import Decimal, InvalidOperation
from datetime import datetime

from django.contrib import messages
from django.http import JsonResponse, HttpResponseNotAllowed, Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone

from admin_panel.decorators import admin_required
from products.models import Product, ProductOffer


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Create and apply a promotional discount offer to a product.
@admin_required
def product_offer(request, product_id):

    # Allow offer creation only through POST requests.
    if request.method != "POST":
        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Only POST requests are allowed."
                },
                status=405
            )

        return redirect("admin_product_list")

    # Find the product or return an appropriate not-found response.
    try:
        product = get_object_or_404(Product, id=product_id)
    except Http404:
        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Product not found."
                },
                status=404
            )
        raise

    # Return validation errors as JSON or preserve HTML messages.
    def validation_error(message):
        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": message
                },
                status=400
            )

        messages.error(request, message)
        return redirect("admin_product_list")

    # Read the submitted offer details.
    offer_name = request.POST.get("offer_name", "").strip()
    discount_input = request.POST.get("discount_value", "").strip()
    start_date_input = request.POST.get("start_date", "").strip()
    end_date_input = request.POST.get("end_date", "").strip()

    # Validate the offer name.
    if not offer_name:
        return validation_error("Offer name is required.")

    # Validate the discount percentage.
    if not discount_input:
        return validation_error("Discount percentage is required.")

    # Validate the offer start date.
    if not start_date_input:
        return validation_error("Start date is required.")

    # Validate the offer end date.
    if not end_date_input:
        return validation_error("End date is required.")

    try:
        discount_value = Decimal(discount_input)
    except (InvalidOperation, ValueError):
        return validation_error("Discount must be a valid number.")

    if not discount_value.is_finite():
        return validation_error("Discount must be a valid number.")

    if discount_value <= 0 or discount_value > 100:
        return validation_error(
            "Discount must be between 1 and 100."
        )

    # Convert the submitted date strings into datetime objects.
    try:
        start_date = datetime.fromisoformat(start_date_input)
        end_date = datetime.fromisoformat(end_date_input)
    except ValueError:
        return validation_error("Invalid date format.")

    # Ensure that the offer ends after it starts.
    if end_date <= start_date:
        return validation_error(
            "End date must be after start date."
        )

    # Deactivate existing active offers for this product.
    ProductOffer.objects.filter(
        product=product,
        is_active=True
    ).update(is_active=False)

    # Create the new active offer.
    offer = ProductOffer.objects.create(
        product=product,
        offer_name=offer_name,
        discount_value=discount_value,
        start_date=start_date,
        end_date=end_date,
        is_active=True
    )

    success_message = "Product offer added successfully."

    # Return the newly created offer to JSON clients.
    if wants_json(request):
        return JsonResponse(
            {
                "success": True,
                "message": success_message,
                "offer": {
                    "id": offer.id,
                    "product_id": product.id,
                    "offer_name": offer.offer_name,
                    "discount_value": str(offer.discount_value),
                    "start_date": offer.start_date.isoformat(),
                    "end_date": offer.end_date.isoformat(),
                    "is_active": offer.is_active
                },
                "redirect_url": reverse("admin_product_list")
            },
            status=201
        )

    # Preserve the existing HTML success message and redirect.
    messages.success(request, success_message)
    return redirect("admin_product_list")


# Activate or deactivate a promotional offer on a product.
@admin_required
def toggle_product_offer(request, offer_id):

    # Require POST because activating or deactivating changes data.
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

    # Find the requested offer.
    try:
        offer = get_object_or_404(ProductOffer, id=offer_id)
    except Http404:
        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Product offer not found."
                },
                status=404
            )
        raise

    # Switch the offer between active and inactive.
    offer.is_active = not offer.is_active
    offer.save(update_fields=["is_active"])

    if offer.is_active:
        success_message = "Product offer activated successfully."
    else:
        success_message = "Product offer deactivated successfully."

    # Return the updated offer status to JSON clients.
    if wants_json(request):
        return JsonResponse(
            {
                "success": True,
                "message": success_message,
                "offer_id": offer.id,
                "product_id": offer.product_id,
                "is_active": offer.is_active,
                "redirect_url": reverse("admin_product_list")
            },
            status=200
        )

    # Preserve the existing HTML success message and redirect.
    messages.success(request, success_message)
    return redirect("admin_product_list")
