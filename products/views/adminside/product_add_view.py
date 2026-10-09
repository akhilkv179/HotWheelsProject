import re
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.core.files.storage import default_storage
from django.shortcuts import render, redirect
from admin_panel.decorators import admin_required
from categories.models import Category
from products.models import Product, ProductVariant, ProductImage



def product_add(request):

    categories = Category.objects.filter(is_active=True)

    if request.method == "POST":

        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        regular_price = request.POST.get("regular_price", "").strip()
        low_stock_threshold = request.POST.get("low_stock_threshold", "").strip()
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

        if not name:
            messages.error(request, "Product name is required.")
            return render(request, "adminside/product_add.html", {"categories": categories})

        if not re.fullmatch(r"[A-Za-z]+(?:\s+[A-Za-z]+)*", name):
            messages.error(request, "Product name must contain only letters and spaces.")
            return render(request, "adminside/product_add.html", {"categories": categories})

        if len(name) > 255:
            messages.error(request, "Product name must not exceed 255 characters.")
            return render(request, "adminside/product_add.html", {"categories": categories})

        if not description:
            messages.error(request, "Product description is required.")
            return render(request, "adminside/product_add.html", {"categories": categories})

        description_word_count = len(description.split())

        if description_word_count < 10:
            messages.error(request, "Product description must contain at least 10 words.")
            return render(request, "adminside/product_add.html", {"categories": categories})

        if not regular_price:
            messages.error(request, "Regular price is required.")
            return render(request, "adminside/product_add.html", {"categories": categories})

        try:
            regular_price = Decimal(regular_price)
        except InvalidOperation:
            messages.error(request, "Regular price must be a valid number.")
            return render(request, "adminside/product_add.html", {"categories": categories})

        if regular_price <= Decimal("0"):
            messages.error(request, "Regular price must be greater than 0.")
            return render(request, "adminside/product_add.html", {"categories": categories})

        if regular_price > Decimal("99999999.99"):
            messages.error(request, "Regular price cannot exceed 99,999,999.99.")
            return render(request, "adminside/product_add.html", {"categories": categories})

        if not low_stock_threshold:
            messages.error(request, "Low stock threshold is required.")
            return render(request, "adminside/product_add.html", {"categories": categories})

        try:
            low_stock_threshold = int(low_stock_threshold)
        except ValueError:
            messages.error(request, "Low stock threshold must be a whole number.")
            return render(request, "adminside/product_add.html", {"categories": categories})

        if low_stock_threshold < 0:
            messages.error(request, "Low stock threshold cannot be negative.")
            return render(request, "adminside/product_add.html", {"categories": categories})

        if low_stock_threshold > 1000000:
            messages.error(request, "Low stock threshold cannot exceed 1,000,000.")
            return render(request, "adminside/product_add.html", {"categories": categories})

        if not category_id:
            messages.error(request, "Please select a category.")
            return render(request, "adminside/product_add.html", {"categories": categories})

        category = Category.objects.filter(
            id=category_id,
            is_active=True
        ).first()

        if not category:
            messages.error(request, "Please select a valid active category.")
            return render(request, "adminside/product_add.html", {"categories": categories})

        if not (
            len(variant_colors)
            == len(variant_sizes)
            == len(variant_prices)
            == len(variant_stocks)
        ):
            messages.error(request, "Invalid variant data.")
            return render(request, "adminside/product_add.html", {"categories": categories})

        if not (
            variant_colors
            and variant_sizes
            and variant_prices
            and variant_stocks
        ):
            messages.error(request, "Please add at least one product variant.")
            return render(request, "adminside/product_add.html", {"categories": categories})

        #Looping through the variant color for add image#

        for index in range(len(variant_colors)):

            variant_images = request.FILES.getlist(f"variant_images_{index}")

            if len(variant_images) != 3:
                messages.error(request,f"Variant {index + 1} must have exactly 3 images.")
                return render(request,"adminside/product_add.html",{"categories": categories})

            for image in variant_images:
                if image.content_type not in allowed_types:
                    messages.error(request,"Only JPG, PNG, and WEBP images are allowed.")
                    return render(request,"adminside/product_add.html",{"categories": categories})

                if image.size > MAX_IMAGE_SIZE:
                    messages.error(request,"Each image must be 5 MB or smaller.")
                    return render(request,"adminside/product_add.html",{"categories": categories})

        for color, size, price, stock in zip(
            variant_colors,
            variant_sizes,
            variant_prices,
            variant_stocks
        ):

            color = color.strip()
            size = size.strip()

            if not color:
                messages.error(request, "Variant colour is required.")
                return render(request, "adminside/product_add.html", {"categories": categories})

            if not re.fullmatch(r"[A-Za-z]+(?:\s+[A-Za-z]+)*", color):
                messages.error(
                    request,
                    "Variant colour must contain only letters and spaces."
                )
                return render(request, "adminside/product_add.html", {"categories": categories})

            if len(color) > 100:
                messages.error(
                    request,
                    "Variant colour must not exceed 100 characters."
                )
                return render(request, "adminside/product_add.html", {"categories": categories})

            if not size:
                messages.error(request, "Variant size is required.")
                return render(request, "adminside/product_add.html", {"categories": categories})

            try:
                price = Decimal(price)
            except InvalidOperation:
                messages.error(
                    request,
                    "Variant price must be a valid number."
                )
                return render(request, "adminside/product_add.html", {"categories": categories})

            if price <= Decimal("0"):
                messages.error(
                    request,
                    "Variant price must be greater than 0."
                )
                return render(request, "adminside/product_add.html", {"categories": categories})

            if price > Decimal("99999999.99"):
                messages.error(
                    request,
                    "Variant price cannot exceed 99,999,999.99."
                )
                return render(request, "adminside/product_add.html", {"categories": categories})

            try:
                stock = int(stock)
            except ValueError:
                messages.error(
                    request,
                    "Variant stock must be a whole number."
                )
                return render(request, "adminside/product_add.html", {"categories": categories})

            if stock < 0:
                messages.error(
                    request,
                    "Variant stock cannot be negative."
                )
                return render(request, "adminside/product_add.html", {"categories": categories})

            if stock > 1000000:
                messages.error(
                    request,
                    "Variant stock cannot exceed 1,000,000."
                )
                return render(request, "adminside/product_add.html", {"categories": categories})

        product = Product.objects.create(
            name=name,
            description=description,
            regular_price=regular_price,
            low_stock_threshold=low_stock_threshold,
            category=category,
        )

        #enumerate gives each item an index number#

        for index, (color, size, price, stock) in enumerate(
            zip(
                variant_colors,
                variant_sizes,
                variant_prices,
                variant_stocks
            )
        ):

            variant = ProductVariant.objects.create(
                product=product,
                color=color.strip(),
                size=size.strip(),
                price=Decimal(price),
                stock_quantity=int(stock),
            )

            variant_images = request.FILES.getlist(
                f"variant_images_{index}"
            )

            for image_index, image in enumerate(variant_images):

                file_path = f"products/{product.id}/variants/{variant.id}/{image.name}"

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

        messages.success(request, "Product added successfully.")
        return redirect("admin_product_list")

    return render(
        request,
        "adminside/product_add.html",
        {"categories": categories}
    )