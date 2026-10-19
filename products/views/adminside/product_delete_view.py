
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse, HttpResponseNotAllowed
from django.urls import reverse

from products.models import Product
from admin_panel.decorators import admin_required


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Soft delete a product by setting its deleted flag.
@admin_required
def delete_product(request, product_id):

    # Allow only POST requests because this action changes product data.
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

    # Find the product or return a 404 response if it does not exist.
    product = get_object_or_404(Product, id=product_id)

    # Mark the product as deleted without permanently removing it.
    product.is_deleted = True
    product.save(update_fields=["is_deleted"])

    success_message = "Product deleted successfully."

    # Return JSON for AJAX requests.
    if wants_json(request):
        return JsonResponse(
            {
                "success": True,
                "message": success_message,
                "product_id": product.id,
                "redirect_url": reverse("admin_product_list"),
            },
            status=200
        )

    # Preserve the existing HTML response.
    messages.success(request, success_message)
    return redirect("admin_product_list")


# Restore a previously soft-deleted product.
@admin_required
def restore_product(request, product_id):

    # Allow only POST requests because this action changes product data.
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

    # Find the product or return a 404 response if it does not exist.
    product = get_object_or_404(Product, id=product_id)

    # Remove the deleted flag to make the product available again.
    product.is_deleted = False
    product.save(update_fields=["is_deleted"])

    success_message = "Product restored successfully."

    # Return JSON for AJAX requests.
    if wants_json(request):
        return JsonResponse(
            {
                "success": True,
                "message": success_message,
                "product_id": product.id,
                "redirect_url": reverse("admin_product_list"),
            },
            status=200
        )

    # Preserve the existing HTML response.
    messages.success(request, success_message)
    return redirect("admin_product_list")
