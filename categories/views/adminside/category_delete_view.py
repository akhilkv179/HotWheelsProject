from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse, HttpResponseNotAllowed
from django.urls import reverse

from admin_panel.decorators import admin_required
from categories.models import Category


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Soft delete a category by setting its deleted flag.
@admin_required
def category_delete(request, category_id):

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

    category.is_deleted = True
    category.save(update_fields=["is_deleted"])

    success_message = "Category deleted successfully."

    if wants_json(request):
        return JsonResponse(
            {
                "success": True,
                "message": success_message,
                "category_id": category.id,
                "redirect_url": reverse("admin_category_list")
            },
            status=200
        )

    messages.success(request, success_message)
    return redirect("admin_category_list")


# Toggle category listing status between active and inactive.
@admin_required
def category_unlisting(request, category_id):

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

    category.is_active = not category.is_active
    category.save(update_fields=["is_active"])

    if category.is_active:
        success_message = "Category listed successfully."
    else:
        success_message = "Category unlisted successfully."

    if wants_json(request):
        return JsonResponse(
            {
                "success": True,
                "message": success_message,
                "category_id": category.id,
                "is_active": category.is_active,
                "redirect_url": reverse("admin_category_list")
            },
            status=200
        )

    messages.success(request, success_message)
    return redirect("admin_category_list")


# Restore a previously soft-deleted category.
@admin_required
def category_restore(request, category_id):

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

    category.is_deleted = False
    category.save(update_fields=["is_deleted"])

    success_message = "Category restored successfully."

    if wants_json(request):
        return JsonResponse(
            {
                "success": True,
                "message": success_message,
                "category_id": category.id,
                "redirect_url": reverse("admin_category_list")
            },
            status=200
        )

    messages.success(request, success_message)
    return redirect("admin_category_list")