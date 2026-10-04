from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from admin_panel.decorators import admin_required
from products.models import Product, ProductVariant, ProductImage
from decimal import Decimal, InvalidOperation
from django.core.files.storage import default_storage



def product_edit(request, product_id):

    product = get_object_or_404(Product, id=product_id)
    variants = product.variants.all()
    images = ProductImage.objects.filter(
        product_variant__product=product
    ).order_by("sort_order")

    if request.method == "POST":

        delete_product = request.POST.get("delete_product")

        if delete_product:
            product.is_active = False
            product.save()
            messages.success(request, "Product deleted successfully.")
            return redirect("admin_product_list")

        delete_variant = request.POST.get("delete_variant")
        delete_image = request.POST.get("delete_image")
        set_primary_image = request.POST.get("set_primary_image")

        if delete_variant:

            variant = get_object_or_404(
                product.variants,
                id=delete_variant
            )

            variant.delete()

            messages.success(
                request,
                "Variant removed successfully."
            )

            return redirect(
                "admin_product_edit",
                product_id=product.id
            )

        if delete_image:

            image = get_object_or_404(
                ProductImage,
                id=delete_image,
                product_variant__product=product
            )

            image_count = ProductImage.objects.filter(
                product_variant__product=product
            ).count()

            if image_count <= 3:
                messages.error(
                    request,
                    "A product must have at least 3 images."
                )

                return redirect(
                    "admin_product_edit",
                    product_id=product.id
                )

            if image.image_url:
                default_storage.delete(image.image_url)

            image.delete()

            remaining_images = ProductImage.objects.filter(
                product_variant__product=product
            ).order_by("sort_order")

            if remaining_images.exists() and not remaining_images.filter(
                is_primary=True
            ).exists():

                primary_image = remaining_images.first()
                primary_image.is_primary = True
                primary_image.save()

            messages.success(
                request,
                "Image removed successfully."
            )

            return redirect(
                "admin_product_edit",
                product_id=product.id
            )

        if set_primary_image:

            image = get_object_or_404(
                ProductImage,
                id=set_primary_image,
                product_variant__product=product
            )

            ProductImage.objects.filter(
                product_variant__product=product
            ).update(is_primary=False)

            image.is_primary = True
            image.save()

            messages.success(
                request,
                "Primary image updated successfully."
            )

            return redirect(
                "admin_product_edit",
                product_id=product.id
            )

        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        regular_price = request.POST.get("regular_price", "").strip()
        low_stock_threshold = request.POST.get(
            "low_stock_threshold",
            ""
        ).strip()

        variant_ids = request.POST.getlist("variant_id[]")
        variant_colors = request.POST.getlist("variant_color[]")
        variant_sizes = request.POST.getlist("variant_size[]")
        variant_prices = request.POST.getlist("variant_price[]")
        variant_stocks = request.POST.getlist("variant_stock[]")

        product_images = request.FILES.getlist("product_images")

        existing_image_count = ProductImage.objects.filter(
            product_variant__product=product
        ).count()

        total_image_count = (
            existing_image_count + len(product_images)
        )

        if total_image_count < 3:
            messages.error(
                request,
                "Product must have at least 3 images."
            )

            return render(
                request,
                "adminside/product_edit.html",
                {
                    "product": product,
                    "variants": variants,
                    "images": images,
                }
            )

        if not name:
            messages.error(
                request,
                "Product name is required."
            )

            return render(
                request,
                "adminside/product_edit.html",
                {
                    "product": product,
                    "variants": variants,
                    "images": images,
                }
            )

        if not description:
            messages.error(
                request,
                "Product description is required."
            )

            return render(
                request,
                "adminside/product_edit.html",
                {
                    "product": product,
                    "variants": variants,
                    "images": images,
                }
            )

        if not regular_price:
            messages.error(
                request,
                "Base price is required."
            )

            return render(
                request,
                "adminside/product_edit.html",
                {
                    "product": product,
                    "variants": variants,
                    "images": images,
                }
            )

        if not low_stock_threshold:
            messages.error(
                request,
                "Low stock threshold is required."
            )

            return render(
                request,
                "adminside/product_edit.html",
                {
                    "product": product,
                    "variants": variants,
                    "images": images,
                }
            )

        try:
            regular_price = Decimal(regular_price)
        except InvalidOperation:

            messages.error(
                request,
                "Base price must be a valid number."
            )

            return render(
                request,
                "adminside/product_edit.html",
                {
                    "product": product,
                    "variants": variants,
                    "images": images,
                }
            )

        if regular_price <= 0:

            messages.error(
                request,
                "Base price must be greater than 0."
            )

            return render(
                request,
                "adminside/product_edit.html",
                {
                    "product": product,
                    "variants": variants,
                    "images": images,
                }
            )

        try:
            low_stock_threshold = int(low_stock_threshold)
        except ValueError:

            messages.error(
                request,
                "Low stock threshold must be a whole number."
            )

            return render(
                request,
                "adminside/product_edit.html",
                {
                    "product": product,
                    "variants": variants,
                    "images": images,
                }
            )

        if low_stock_threshold < 0:

            messages.error(
                request,
                "Low stock threshold cannot be negative."
            )

            return render(
                request,
                "adminside/product_edit.html",
                {
                    "product": product,
                    "variants": variants,
                    "images": images,
                }
            )

        if not (
            len(variant_colors)
            == len(variant_sizes)
            == len(variant_prices)
            == len(variant_stocks)
        ):

            messages.error(
                request,
                "Invalid variant data."
            )

            return render(
                request,
                "adminside/product_edit.html",
                {
                    "product": product,
                    "variants": variants,
                    "images": images,
                }
            )

        if len(variant_ids) > len(variant_colors):

            messages.error(
                request,
                "Invalid variant IDs."
            )

            return render(
                request,
                "adminside/product_edit.html",
                {
                    "product": product,
                    "variants": variants,
                    "images": images,
                }
            )

        while len(variant_ids) < len(variant_colors):
            variant_ids.append("")

        for color, size, price, stock in zip(
            variant_colors,
            variant_sizes,
            variant_prices,
            variant_stocks
        ):

            if not color.strip():

                messages.error(
                    request,
                    "Variant colour is required."
                )

                return render(
                    request,
                    "adminside/product_edit.html",
                    {
                        "product": product,
                        "variants": variants,
                        "images": images,
                    }
                )

            if not size.strip():

                messages.error(
                    request,
                    "Variant size is required."
                )

                return render(
                    request,
                    "adminside/product_edit.html",
                    {
                        "product": product,
                        "variants": variants,
                        "images": images,
                    }
                )

            try:
                price = Decimal(price)
            except InvalidOperation:

                messages.error(
                    request,
                    "Variant price must be a valid number."
                )

                return render(
                    request,
                    "adminside/product_edit.html",
                    {
                        "product": product,
                        "variants": variants,
                        "images": images,
                    }
                )

            if price <= 0:

                messages.error(
                    request,
                    "Variant price must be greater than 0."
                )

                return render(
                    request,
                    "adminside/product_edit.html",
                    {
                        "product": product,
                        "variants": variants,
                        "images": images,
                    }
                )

            try:
                stock = int(stock)
            except ValueError:

                messages.error(
                    request,
                    "Variant stock must be a whole number."
                )

                return render(
                    request,
                    "adminside/product_edit.html",
                    {
                        "product": product,
                        "variants": variants,
                        "images": images,
                    }
                )

            if stock < 0:

                messages.error(
                    request,
                    "Variant stock cannot be negative."
                )

                return render(
                    request,
                    "adminside/product_edit.html",
                    {
                        "product": product,
                        "variants": variants,
                        "images": images,
                    }
                )

        if product_images:

            allowed_types = [
                "image/jpeg",
                "image/png",
                "image/webp",
            ]

            MAX_IMAGE_SIZE = 5 * 1024 * 1024

            for image in product_images:

                if image.content_type not in allowed_types:

                    messages.error(
                        request,
                        "Only JPG, PNG, and WEBP images are allowed."
                    )

                    return render(
                        request,
                        "adminside/product_edit.html",
                        {
                            "product": product,
                            "variants": variants,
                            "images": images,
                        }
                    )

                if image.size > MAX_IMAGE_SIZE:

                    messages.error(
                        request,
                        "Each image must be 5 MB or smaller."
                    )

                    return render(
                        request,
                        "adminside/product_edit.html",
                        {
                            "product": product,
                            "variants": variants,
                            "images": images,
                        }
                    )

        product.name = name
        product.description = description
        product.regular_price = regular_price
        product.low_stock_threshold = low_stock_threshold
        product.save()

        for variant_id, color, size, price, stock in zip(
            variant_ids,
            variant_colors,
            variant_sizes,
            variant_prices,
            variant_stocks
        ):

            if variant_id:

                variant = get_object_or_404(
                    product.variants,
                    id=variant_id
                )

                variant.color = color.strip()
                variant.size = size.strip()
                variant.price = Decimal(price)
                variant.stock_quantity = int(stock)

                variant.save()

            else:

                ProductVariant.objects.create(
                    product=product,
                    color=color.strip(),
                    size=size.strip(),
                    price=Decimal(price),
                    stock_quantity=int(stock)
                )

        if product_images:

            first_variant = product.variants.first()

            if not first_variant:

                messages.error(
                    request,
                    "Product must have at least one variant."
                )

                return render(
                    request,
                    "adminside/product_edit.html",
                    {
                        "product": product,
                        "variants": product.variants.all(),
                        "images": images,
                    }
                )

            last_image = ProductImage.objects.filter(
                product_variant__product=product
            ).order_by("-sort_order").first()

            if last_image:
                sort_order = last_image.sort_order + 1
            else:
                sort_order = 0

            for image in product_images:

                file_path = (
                    f"products/{product.id}/{image.name}"
                )

                saved_path = default_storage.save(
                    file_path,
                    image
                )

                ProductImage.objects.create(
                    product_variant=first_variant,
                    image_url=saved_path,
                    is_primary=False,
                    sort_order=sort_order,
                )

                sort_order += 1

        messages.success(
            request,
            "Product updated successfully."
        )

        return redirect("admin_product_list")

    return render(
        request,
        "adminside/product_edit.html",
        {
            "product": product,
            "variants": variants,
            "images": images,
        }
    )