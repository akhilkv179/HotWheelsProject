
import re
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.files.storage import default_storage
from django.http import JsonResponse, HttpResponseNotAllowed, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from admin_panel.decorators import admin_required
from categories.models import Category
from products.models import Product, ProductVariant, ProductImage


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Edit product information, update variants, and manage product images.
@admin_required
def product_edit(request, product_id):

    # Allow GET to display the page and POST to process changes.
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

    # Find the product or return a JSON 404 response for API requests.
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

    categories = Category.objects.filter(
        is_active=True
    ).order_by("name")

    variants = product.variants.all()

    # Find images belonging to variants of this product.
    images = ProductImage.objects.filter(
        product_variant__product=product
    ).order_by("product_variant_id", "sort_order")

    # Keep the existing template context for HTML responses.
    def page_context():
        return {
            "product": product,
            "categories": categories,
            "variants": product.variants.all(),
            "images": ProductImage.objects.filter(
                product_variant__product=product
            ).order_by("product_variant_id", "sort_order"),
        }

    # Return validation errors as JSON or display them in the HTML page.
    def fail(message, status=400, redirect_back=False):
        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": message,
                },
                status=status
            )

        messages.error(request, message)

        if redirect_back:
            return redirect(
                "admin_product_edit",
                product_id=product.id
            )

        return render(
            request,
            "adminside/product_edit.html",
            page_context()
        )

    # Return successful actions as JSON or preserve the HTML redirect.
    def succeed(message, status=200, redirect_to_list=False):
        if wants_json(request):
            return JsonResponse(
                {
                    "success": True,
                    "message": message,
                    "product_id": product.id,
                    "redirect_url": reverse(
                        "admin_product_list"
                        if redirect_to_list
                        else "admin_product_edit",
                        **(
                            {}
                            if redirect_to_list
                            else {"kwargs": {"product_id": product.id}}
                        )
                    ),
                },
                status=status
            )

        messages.success(request, message)

        if redirect_to_list:
            return redirect("admin_product_list")

        return redirect(
            "admin_product_edit",
            product_id=product.id
        )

    # Return product details when a client requests JSON.
    if request.method == "GET":
        if wants_json(request):
            return JsonResponse(
                {
                    "success": True,
                    "product": {
                        "id": product.id,
                        "name": product.name,
                        "description": product.description,
                        "regular_price": str(product.regular_price),
                        "low_stock_threshold": product.low_stock_threshold,
                        "category_id": product.category_id,
                        "is_active": product.is_active,
                        "is_deleted": product.is_deleted,
                    },
                    "categories": [
                        {
                            "id": category.id,
                            "name": category.name,
                        }
                        for category in categories
                    ],
                    "variants": [
                        {
                            "id": variant.id,
                            "color": variant.color,
                            "size": variant.size,
                            "price": str(variant.price),
                            "stock_quantity": variant.stock_quantity,
                        }
                        for variant in variants
                    ],
                    "images": [
                        {
                            "id": image.id,
                            "variant_id": image.product_variant_id,
                            "image_url": str(image.image_url),
                            "is_primary": image.is_primary,
                            "sort_order": image.sort_order,
                        }
                        for image in images
                    ],
                },
                status=200
            )

        return render(
            request,
            "adminside/product_edit.html",
            page_context()
        )

    # Handle product deactivation.
    delete_product = request.POST.get("delete_product")

    if delete_product:
        product.is_active = False
        product.save(update_fields=["is_active"])

        return succeed(
            "Product deleted successfully.",
            redirect_to_list=True
        )

    # Handle variant deletion, image deletion, and primary image selection.
    delete_variant = request.POST.get("delete_variant")
    delete_image = request.POST.get("delete_image")
    set_primary_image = request.POST.get("set_primary_image")

    if delete_variant:
        try:
            variant = get_object_or_404(
                product.variants,
                id=delete_variant
            )
        except Http404:
            return fail("Variant not found.", status=404)

        variant.delete()

        return succeed("Variant removed successfully.")

    if delete_image:
        try:
            image = get_object_or_404(
                ProductImage,
                id=delete_image,
                product_variant__product=product
            )
        except Http404:
            return fail("Image not found.", status=404)

        variant = image.product_variant

        # Ensure the variant retains at least three images.
        variant_image_count = ProductImage.objects.filter(
            product_variant=variant
        ).count()

        if variant_image_count <= 3:
            return fail(
                "Each variant must have exactly 3 images.",
                redirect_back=True
            )

        if image.image_url:
            default_storage.delete(image.image_url)

        was_primary = image.is_primary
        image.delete()

        remaining_images = ProductImage.objects.filter(
            product_variant=variant
        ).order_by("sort_order")

        # Assign a replacement primary image if the primary was removed.
        if remaining_images.exists() and was_primary:
            primary_image = remaining_images.first()
            primary_image.is_primary = True
            primary_image.save(update_fields=["is_primary"])

        return succeed("Image removed successfully.")

    if set_primary_image:
        try:
            image = get_object_or_404(
                ProductImage,
                id=set_primary_image,
                product_variant__product=product
            )
        except Http404:
            return fail("Image not found.", status=404)

        # Clear the primary-image flag for this variant's other images.
        ProductImage.objects.filter(
            product_variant=image.product_variant
        ).update(is_primary=False)

        image.is_primary = True
        image.save(update_fields=["is_primary"])

        return succeed("Primary image updated successfully.")

    # Collect the submitted product and variant details.
    name = request.POST.get("name", "").strip()
    description = request.POST.get("description", "").strip()
    regular_price_input = request.POST.get("regular_price", "").strip()
    threshold_input = request.POST.get("low_stock_threshold", "").strip()
    category_id = request.POST.get("category", "").strip()

    variant_ids = request.POST.getlist("variant_id[]")
    variant_colors = request.POST.getlist("variant_color[]")
    variant_sizes = request.POST.getlist("variant_size[]")
    variant_prices = request.POST.getlist("variant_price[]")
    variant_stocks = request.POST.getlist("variant_stock[]")

    # Check that the variant fields contain matching numbers of values.
    if not (
        len(variant_colors)
        == len(variant_sizes)
        == len(variant_prices)
        == len(variant_stocks)
    ):
        return fail("Invalid variant data.")

    if not variant_colors:
        return fail("Please add at least one product variant.")

    if len(variant_ids) > len(variant_colors):
        return fail("Invalid variant IDs.")

    # Empty IDs represent newly added variants.
    while len(variant_ids) < len(variant_colors):
        variant_ids.append("")

    # Validate the product name.
    if not name:
        return fail("Product name is required.")

    if not re.fullmatch(r"[A-Za-z]+(?:\s+[A-Za-z]+)*", name):
        return fail(
            "Product name must contain only letters and spaces."
        )

    if len(name) > 255:
        return fail(
            "Product name must not exceed 255 characters."
        )

    # Validate the description.
    if not description:
        return fail("Product description is required.")

    if len(description.split()) < 10:
        return fail(
            "Product description must contain at least 10 words."
        )

    # Validate the regular price.
    if not regular_price_input:
        return fail("Regular price is required.")

    try:
        regular_price = Decimal(regular_price_input)
    except (InvalidOperation, ValueError):
        return fail("Regular price must be a valid number.")

    if not regular_price.is_finite():
        return fail("Regular price must be a valid number.")

    if regular_price <= Decimal("0"):
        return fail("Regular price must be greater than 0.")

    if regular_price > Decimal("99999999.99"):
        return fail(
            "Regular price cannot exceed 99,999,999.99."
        )

    # Validate the low-stock threshold.
    if not threshold_input:
        return fail("Low stock threshold is required.")

    try:
        low_stock_threshold = int(threshold_input)
    except (ValueError, TypeError):
        return fail(
            "Low stock threshold must be a whole number."
        )

    if low_stock_threshold < 0:
        return fail("Low stock threshold cannot be negative.")

    if low_stock_threshold > 1000000:
        return fail(
            "Low stock threshold cannot exceed 1,000,000."
        )

    # Check that the selected category exists and is active.
    if not category_id:
        return fail("Please select a category.")

    category = Category.objects.filter(
        id=category_id,
        is_active=True
    ).first()

    if not category:
        return fail("Please select a valid active category.")

    # Validate every variant before saving product changes.
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
            return fail("Variant colour is required.")

        if not re.fullmatch(r"[A-Za-z]+(?:\s+[A-Za-z]+)*", color):
            return fail(
                "Variant colour must contain only letters and spaces."
            )

        if len(color) > 100:
            return fail(
                "Variant colour must not exceed 100 characters."
            )

        if not size:
            return fail("Variant size is required.")

        try:
            price = Decimal(price_input)
        except (InvalidOperation, ValueError):
            return fail(
                "Variant price must be a valid number."
            )

        if not price.is_finite():
            return fail(
                "Variant price must be a valid number."
            )

        if price <= Decimal("0"):
            return fail(
                "Variant price must be greater than 0."
            )

        if price > Decimal("99999999.99"):
            return fail(
                "Variant price cannot exceed 99,999,999.99."
            )

        try:
            stock = int(stock_input)
        except (ValueError, TypeError):
            return fail(
                "Variant stock must be a whole number."
            )

        if stock < 0:
            return fail("Variant stock cannot be negative.")

        if stock > 1000000:
            return fail(
                "Variant stock cannot exceed 1,000,000."
            )

        validated_variants.append({
            "color": color,
            "size": size,
            "price": price,
            "stock": stock,
        })

    # Validate uploaded images before saving changes.
    new_images_by_variant = []

    for index, variant_id in enumerate(variant_ids):
        new_images = request.FILES.getlist(
            f"variant_images_{index}"
        )

        if variant_id:
            try:
                variant = get_object_or_404(
                    product.variants,
                    id=variant_id
                )
            except Http404:
                return fail(
                    f"Variant {index + 1} was not found.",
                    status=404
                )
        else:
            variant = None

        # Preserve the existing rule allowing additional images
        # without enforcing exactly three images on every edit.
        for image in new_images:
            if image.content_type not in [
                "image/jpeg",
                "image/png",
                "image/webp",
            ]:
                return fail(
                    "Only JPG, PNG, and WEBP images are allowed."
                )

            if image.size > 5 * 1024 * 1024:
                return fail(
                    "Each image must be 5 MB or smaller."
                )

        new_images_by_variant.append(new_images)

    # Save the product details.
    product.name = name
    product.description = description
    product.regular_price = regular_price
    product.low_stock_threshold = low_stock_threshold
    product.category = category
    product.save()

    # Update existing variants or create new variants.
    updated_variants = []

    for index, (variant_id, variant_data) in enumerate(
        zip(variant_ids, validated_variants)
    ):
        if variant_id:
            variant = get_object_or_404(
                product.variants,
                id=variant_id
            )

            variant.color = variant_data["color"]
            variant.size = variant_data["size"]
            variant.price = variant_data["price"]
            variant.stock_quantity = variant_data["stock"]
            variant.save()
        else:
            variant = ProductVariant.objects.create(
                product=product,
                color=variant_data["color"],
                size=variant_data["size"],
                price=variant_data["price"],
                stock_quantity=variant_data["stock"],
            )

        updated_variants.append({
            "id": variant.id,
            "color": variant.color,
            "size": variant.size,
            "price": str(variant.price),
            "stock_quantity": variant.stock_quantity,
        })

        # Save newly uploaded images for this variant.
        new_images = new_images_by_variant[index]

        if not new_images:
            continue

        last_image = ProductImage.objects.filter(
            product_variant=variant
        ).order_by("-sort_order").first()

        sort_order = (
            last_image.sort_order + 1
            if last_image
            else 0
        )

        has_primary = ProductImage.objects.filter(
            product_variant=variant,
            is_primary=True
        ).exists()

        for image_index, image in enumerate(new_images):
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
                is_primary=(
                    not has_primary and image_index == 0
                ),
                sort_order=sort_order,
            )

            sort_order += 1

    # Return a JSON success response or the original HTML redirect.
    if wants_json(request):
        return JsonResponse(
            {
                "success": True,
                "message": "Product updated successfully.",
                "product": {
                    "id": product.id,
                    "name": product.name,
                    "description": product.description,
                    "regular_price": str(product.regular_price),
                    "low_stock_threshold": product.low_stock_threshold,
                    "category_id": product.category_id,
                },
                "variants": updated_variants,
                "redirect_url": reverse("admin_product_list"),
            },
            status=200
        )

    messages.success(request, "Product updated successfully.")
    return redirect("admin_product_list")
