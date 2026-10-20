from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import JsonResponse, HttpResponseNotAllowed
from django.urls import reverse

from admin_panel.decorators import admin_required
from categories.models import Category


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Create and save a new product category in the admin panel.
@admin_required
def category_add(request):

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

    name = request.POST.get("name", "").strip()
    description = request.POST.get("description", "").strip()
    image = request.FILES.get("image")

    if not name:
        error_message = "Category name is required."

        if wants_json(request):
            return JsonResponse(
                {"success": False, "message": error_message},
                status=400
            )

        messages.error(request, error_message)
        return redirect("admin_category_list")

    if not description:
        error_message = "Category description is required."

        if wants_json(request):
            return JsonResponse(
                {"success": False, "message": error_message},
                status=400
            )

        messages.error(request, error_message)
        return redirect("admin_category_list")

    # Image is optional, preserving your existing behavior.

    if Category.objects.filter(name__iexact=name).exists():
        error_message = "A category with this name already exists."

        if wants_json(request):
            return JsonResponse(
                {"success": False, "message": error_message},
                status=409
            )

        messages.error(request, error_message)
        return redirect("admin_category_list")

    category = Category.objects.create(
        name=name,
        description=description,
        image=image
    )

    success_message = "Category added successfully."

    if wants_json(request):
        return JsonResponse(
            {
                "success": True,
                "message": success_message,
                "category": {
                    "id": category.id,
                    "name": category.name,
                    "description": category.description,
                },
                "redirect_url": reverse("admin_category_list")
            },
            status=201
        )

    messages.success(request, success_message)
    return redirect("admin_category_list")