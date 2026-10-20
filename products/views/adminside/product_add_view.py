
import re
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.files.storage import default_storage
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render, redirect
from django.urls import reverse

from admin_panel.decorators import admin_required
from categories.models import Category
from products.models import Product, ProductVariant, ProductImage


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Create a new product with multiple variants and uploaded images.
@admin_required
def product_add(request):

    categories = Category.objects.filter(is_active=True)

    # Support GET for displaying the form and POST for creating a product.
    if request.method not in ["GET", "POST"]:
        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Only GET and POST requests are allowed."
                },
                status=405
            )

        return HttpResponseNotAllowed(["GET", "POST"])

    # JSON response for the form's category data.
    if request.method == "GET":
        if wants_json(request):
            return JsonResponse(
                {
                    "success": True,
                    "categories": [
                        {
                            "id": category.id,
                            "name": category.name
                        }
                        for category in categories
                    ]
                },
                status=200
            )

        return render(
            request,
            "adminside/product_add.html",
            {"categories": categories}
        )

    # Return validation errors in JSON or preserve the HTML form behavior.
    def validation_error(message, status=400):
        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": message
                },
                status=status
            )

        messages.error(request, message)
        return render(
            request,
            "adminside/product_add.html",
            {"categories": categories}
        )

    name = request.POST.get("name", "").strip()
    description = request.POST.get("description", "").strip()
    regular_price_input = request.POST.get("regular_price", "").strip()
    threshold_input = request.POST.get("low_stock_threshold", "").strip()
    category_id = request.POST.get("category", "").strip()

    variant_colors = request.POST.getlist("variant_color[]")
    variant_sizes = request.POST.getlist("variant_size[]")
    variant_prices = request.POST.getlist("variant_price[]")
    variant_stocks = request.POST.getlist("variant_stock[]")

    MAX_IMAGE_SIZE = 5 * 1024 * 1024

    allowed_types = [
        "image/jpeg",
        "image/png",
        "image/webp",
    ]

    # Validate product name.
    if not name:
        return validation_error("Product name is required.")

    if not re.fullmatch(r"[A-Za-z]+(?:\s+[A-Za-z]+)*", name):
        return validation_error(
            "Product name must contain only letters and spaces."
        )

    if len(name) > 255:
        return validation_error(
            "Product name must not exceed 255 characters."
        )

    # Validate description.
    if not description:
        return validation_error("Product description is required.")

    description_word_count = len(description.split())

    if description_word_count < 10:
        return validation_error(
            "Product description must contain at least 10 words."
        )

    # Validate regular price.
    if not regular_price_input:
        return validation_error("Regular price is required.")

    try:
        regular_price = Decimal(regular_price_input)
    except (InvalidOperation, ValueError):
        return validation_error(
            "Regular price must be a valid number."
        )

    if not regular_price.is_finite():
        return validation_error(
            "Regular price must be a valid number."
        )

    if regular_price <= Decimal("0"):
        return validation_error(
            "Regular price must be greater than 0."
        )

    if regular_price > Decimal("99999999.99"):
        return validation_error(
            "Regular price cannot exceed 99,999,999.99."
        )

    # Validate low-stock threshold.
    if not threshold_input:
        return validation_error(
            "Low stock threshold is required."
        )

    try:
        low_stock_threshold = int(threshold_input)
    except (ValueError, TypeError):
        return validation_error(
            "Low stock threshold must be a whole number."
        )

    if low_stock_threshold < 0:
        return validation_error(
            "Low stock threshold cannot be negative."
        )

    if low_stock_threshold > 1000000:
        return validation_error(
            "Low stock threshold cannot exceed 1,000,000."
        )

    # Validate category.
    if not category_id:
        return validation_error("Please select a category.")

    category = Category.objects.filter(
        id=category_id,
        is_active=True
    ).first()

    if not category:
        return validation_error(
            "Please select a valid active category."
        )

    # Validate the number of fields supplied for each variant.
    if not (
        len(variant_colors)
        == len(variant_sizes)
        == len(variant_prices)
        == len(variant_stocks)
    ):
        return validation_error("Invalid variant data.")

    if not variant_colors:
        return validation_error(
            "Please add at least one product variant."
        )

    # Validate exactly three images for every variant.
    all_variant_images = []

    for index in range(len(variant_colors)):
        variant_images = request.FILES.getlist(
            f"variant_images_{index}"
        )

        if len(variant_images) != 3:
            return validation_error(
                f"Variant {index + 1} must have exactly 3 images."
            )

        for image in variant_images:
            if image.content_type not in allowed_types:
                return validation_error(
                    "Only JPG, PNG, and WEBP images are allowed."
                )

            if image.size > MAX_IMAGE_SIZE:
                return validation_error(
                    "Each image must be 5 MB or smaller."
                )

        all_variant_images.append(variant_images)

    # Validate every variant before creating the product.
    validated_variants = []

    for color, size, price_input, stock_input in zip(
        variant_colors,
        variant_sizes,
        variant_prices,
        variant_stocks
    ):
        color = color.strip()
        size = size.strip()

        if not color:
            return validation_error(
                "Variant colour is required."
            )

        if not re.fullmatch(r"[A-Za-z]+(?:\s+[A-Za-z]+)*", color):
            return validation_error(
                "Variant colour must contain only letters and spaces."
            )

        if len(color) > 100:
            return validation_error(
                "Variant colour must not exceed 100 characters."
            )

        if not size:
            return validation_error(
                "Variant size is required."
            )

        try:
            price = Decimal(price_input)
        except (InvalidOperation, ValueError):
            return validation_error(
                "Variant price must be a valid number."
            )

        if not price.is_finite():
            return validation_error(
                "Variant price must be a valid number."
            )

        if price <= Decimal("0"):
            return validation_error(
                "Variant price must be greater than 0."
            )

        if price > Decimal("99999999.99"):
            return validation_error(
                "Variant price cannot exceed 99,999,999.99."
            )

        try:
            stock = int(stock_input)
        except (ValueError, TypeError):
            return validation_error(
                "Variant stock must be a whole number."
            )

        if stock < 0:
            return validation_error(
                "Variant stock cannot be negative."
            )

        if stock > 1000000:
            return validation_error(
                "Variant stock cannot exceed 1,000,000."
            )

        validated_variants.append({
            "color": color,
            "size": size,
            "price": price,
            "stock": stock,
        })

    # All validation passed. Create the product and its variants.
    product = Product.objects.create(
        name=name,
        description=description,
        regular_price=regular_price,
        low_stock_threshold=low_stock_threshold,
        category=category,
    )

    created_variants = []

    for index, variant_data in enumerate(validated_variants):
        variant = ProductVariant.objects.create(
            product=product,
            color=variant_data["color"],
            size=variant_data["size"],
            price=variant_data["price"],
            stock_quantity=variant_data["stock"],
        )

        created_variants.append({
            "id": variant.id,
            "color": variant.color,
            "size": variant.size,
            "price": str(variant.price),
            "stock_quantity": variant.stock_quantity,
        })

        variant_images = all_variant_images[index]

        for image_index, image in enumerate(variant_images):
            file_path = (
                f"products/{product.id}/variants/"
                f"{variant.id}/{image.name}"
            )

            saved_path = default_storage.save(
                file_path,
                image
            )

            ProductImage.objects.create(
                product_variant=variant,
                image_url=saved_path,
                is_primary=(image_index == 0),
                sort_order=image_index,
            )

    success_message = "Product added successfully."

    if wants_json(request):
        return JsonResponse(
            {
                "success": True,
                "message": success_message,
                "product": {
                    "id": product.id,
                    "name": product.name,
                    "description": product.description,
                    "regular_price": str(product.regular_price),
                    "low_stock_threshold": product.low_stock_threshold,
                    "category_id": category.id,
                    "category_name": category.name,
                    "variants": created_variants,
                },
                "redirect_url": reverse("admin_product_list"),
            },
            status=201
        )

    messages.success(request, success_message)
    return redirect("admin_product_list")
