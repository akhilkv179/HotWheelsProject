import re
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.core.files.storage import default_storage
from django.shortcuts import get_object_or_404, redirect, render
from admin_panel.decorators import admin_required
from categories.models import Category
from products.models import Product, ProductVariant, ProductImage



def product_edit(request, product_id):

    product = get_object_or_404(Product, id=product_id)

    categories = Category.objects.filter(
        is_active=True
    ).order_by("name")

    variants = product.variants.all()

    #Find only the images whose variant belongs to this product.#
    images = ProductImage.objects.filter(
        product_variant__product=product
    ).order_by("product_variant_id", "sort_order")

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

            variant = get_object_or_404(product.variants,id=delete_variant)
            variant.delete()

            messages.success(request,"Variant removed successfully.")
            return redirect("admin_product_edit",product_id=product.id)

        if delete_image:
            image = get_object_or_404(ProductImage,id=delete_image,product_variant__product=product)

            variant = image.product_variant

            #counting the image for checking there is 3 image if yes continue no erro message# 
            variant_image_count = ProductImage.objects.filter(
                product_variant=variant
            ).count()

            if variant_image_count <= 3:
                messages.error(request,"Each variant must have exactly 3 images.")
                return redirect("admin_product_edit",product_id=product.id)

            if image.image_url:
                default_storage.delete(image.image_url)
                #default_storage is Django's built-in interface for storing uploaded files 
                # using whatever storage system your project is configured to use.#

            was_primary = image.is_primary

            image.delete()

            remaining_images = ProductImage.objects.filter(
                product_variant=variant
            ).order_by("sort_order")

            if remaining_images.exists() and was_primary:
                primary_image = remaining_images.first()
                primary_image.is_primary = True
                primary_image.save(update_fields=["is_primary"])

            messages.success(request,"Image removed successfully.")
            return redirect("admin_product_edit",product_id=product.id)

        if set_primary_image:

            image = get_object_or_404(
                ProductImage,
                id=set_primary_image,
                product_variant__product=product
            )

            ProductImage.objects.filter(
                product_variant=image.product_variant
            ).update(is_primary=False)

            image.is_primary = True
            image.save(update_fields=["is_primary"])

            messages.success(request,"Primary image updated successfully.")

            return redirect("admin_product_edit",product_id=product.id)

        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        regular_price = request.POST.get( "regular_price","").strip()
        low_stock_threshold = request.POST.get("low_stock_threshold","").strip()
        category_id = request.POST.get("category","").strip()
        variant_ids = request.POST.getlist("variant_id[]")
        variant_colors = request.POST.getlist("variant_color[]")
        variant_sizes = request.POST.getlist("variant_size[]")
        variant_prices = request.POST.getlist("variant_price[]")
        variant_stocks = request.POST.getlist("variant_stock[]")

        if not (len(variant_colors)== len(variant_sizes)== len(variant_prices)== len(variant_stocks)):
            messages.error(request,"Invalid variant data.")

            return render(request,"adminside/product_edit.html",{
                    "product": product,
                    "categories": categories,
                    "variants": variants,
                    "images": images,
                }
            )

        if not variant_colors:
            messages.error(request,"Please add at least one product variant.")

            return render(request,"adminside/product_edit.html",
                {
                    "product": product,
                    "categories": categories,
                    "variants": variants,
                    "images": images,
                }
            )

        if len(variant_ids) > len(variant_colors):
            messages.error(request,"Invalid variant IDs.")

            return render(request,"adminside/product_edit.html",
                {
                    "product": product,
                    "categories": categories,
                    "variants": variants,
                    "images": images,
                }
            )

        while len(variant_ids) < len(variant_colors):
            variant_ids.append("")

        if not name:
            messages.error(request,"Product name is required.")

            return render(request,"adminside/product_edit.html",
                {
                    "product": product,
                    "categories": categories,
                    "variants": variants,
                    "images": images,
                }
            )

        if not re.fullmatch(
            r"[A-Za-z]+(?:\s+[A-Za-z]+)*",
            name
        ):
            messages.error(request,"Product name must contain only letters and spaces.")
            return render(request,"adminside/product_edit.html",
                {
                    "product": product,
                    "categories": categories,
                    "variants": variants,
                    "images": images,
                }
            )

        if len(name) > 255:
            messages.error(request,"Product name must not exceed 255 characters.")
            return render(request,
                "adminside/product_edit.html",
                {
                    "product": product,
                    "categories": categories,
                    "variants": variants,
                    "images": images,
                }
            )

        if not description:
            messages.error(request,
                "Product description is required."
            )

            return render(request,"adminside/product_edit.html",
                {
                    "product": product,
                    "categories": categories,
                    "variants": variants,
                    "images": images,
                }
            )

        if len(description.split()) < 10:
            messages.error(request,"Product description must contain at least 10 words.")
            return render(request,"adminside/product_edit.html",
                {
                    "product": product,
                    "categories": categories,
                    "variants": variants,
                    "images": images,
                }
            )

        if not regular_price:
            messages.error(request,"Regular price is required.")
            return render(request,"adminside/product_edit.html",
                {
                    "product": product,
                    "categories": categories,
                    "variants": variants,
                    "images": images,
                }
            )

        try:
            regular_price = Decimal(regular_price)
        except InvalidOperation:
            messages.error(request,"Regular price must be a valid number.")

            return render(request,"adminside/product_edit.html",
                {
                    "product": product,
                    "categories": categories,
                    "variants": variants,
                    "images": images,
                }
            )

        if regular_price <= Decimal("0"):
            messages.error(
                request,
                "Regular price must be greater than 0."
            )

            return render(request,"adminside/product_edit.html",
                {
                    "product": product,
                    "categories": categories,
                    "variants": variants,
                    "images": images,
                }
            )

        if regular_price > Decimal("99999999.99"):
            messages.error(request,"Regular price cannot exceed 99,999,999.99.")
            return render(request,"adminside/product_edit.html",
                {
                    "product": product,
                    "categories": categories,
                    "variants": variants,
                    "images": images,
                }
            )

        if not low_stock_threshold:
            messages.error(request,"Low stock threshold is required.")

            return render(request,"adminside/product_edit.html",
                {
                    "product": product,
                    "categories": categories,
                    "variants": variants,
                    "images": images,
                }
            )

        try:
            low_stock_threshold = int(low_stock_threshold)
        except ValueError:
            messages.error(request,"Low stock threshold must be a whole number.")
            return render(request,"adminside/product_edit.html",
                {
                    "product": product,
                    "categories": categories,
                    "variants": variants,
                    "images": images,
                }
            )

        if low_stock_threshold < 0:
            messages.error(request,"Low stock threshold cannot be negative.")
            return render(request,"adminside/product_edit.html",
                {
                    "product": product,
                    "categories": categories,
                    "variants": variants,
                    "images": images,
                }
            )

        if low_stock_threshold > 1000000:
            messages.error(request,"Low stock threshold cannot exceed 1,000,000.")
            return render(request,"adminside/product_edit.html",
                {
                    "product": product,
                    "categories": categories,
                    "variants": variants,
                    "images": images,
                }
            )

        if not category_id:
            messages.error(request,"Please select a category.")
            return render(request,"adminside/product_edit.html",
                {
                    "product": product,
                    "categories": categories,
                    "variants": variants,
                    "images": images,
                }
            )

        category = Category.objects.filter(
            id=category_id,
            is_active=True
        ).first()

        if not category:
            messages.error(request,"Please select a valid active category.")
            return render(request,"adminside/product_edit.html",
                {
                    "product": product,
                    "categories": categories,
                    "variants": variants,
                    "images": images,
                }
            )

        for color, size, price, stock in zip(
            variant_colors,
            variant_sizes,
            variant_prices,
            variant_stocks
        ):

            color = color.strip()
            size = size.strip()

            if not color:
                messages.error(request,"Variant colour is required.")
                return render(request,"adminside/product_edit.html",
                    {
                        "product": product,
                        "categories": categories,
                        "variants": variants,
                        "images": images,
                    }
                )

            if not re.fullmatch(
                r"[A-Za-z]+(?:\s+[A-Za-z]+)*",
                color
            ):
                messages.error(request,"Variant colour must contain only letters and spaces.")
                return render(request,"adminside/product_edit.html",
                    {
                        "product": product,
                        "categories": categories,
                        "variants": variants,
                        "images": images,
                    }
                )

            if len(color) > 100:
                messages.error(request,"Variant colour must not exceed 100 characters.")
                return render(request,"adminside/product_edit.html",
                    {
                        "product": product,
                        "categories": categories,
                        "variants": variants,
                        "images": images,
                    }
                )

            if not size:
                messages.error(request,"Variant size is required.")
                return render(request,"adminside/product_edit.html",
                    {
                        "product": product,
                        "categories": categories,
                        "variants": variants,
                        "images": images,
                    }
                )

            try:
                price = Decimal(price)
            except InvalidOperation:
                messages.error(request,"Variant price must be a valid number.")
                return render(request,"adminside/product_edit.html",
                    {
                        "product": product,
                        "categories": categories,
                        "variants": variants,
                        "images": images,
                    }
                )

            if price <= Decimal("0"):
                messages.error(request,"Variant price must be greater than 0.")
                return render(request,"adminside/product_edit.html",
                    {
                        "product": product,
                        "categories": categories,
                        "variants": variants,
                        "images": images,
                    }
                )

            if price > Decimal("99999999.99"):
                messages.error(request,"Variant price cannot exceed 99,999,999.99.")
                return render(request,"adminside/product_edit.html",
                    {
                        "product": product,
                        "categories": categories,
                        "variants": variants,
                        "images": images,
                    }
                )

            try:
                stock = int(stock)
            except ValueError:
                messages.error(request,"Variant stock must be a whole number.")
                return render(request,"adminside/product_edit.html",
                    {
                        "product": product,
                        "categories": categories,
                        "variants": variants,
                        "images": images,
                    }
                )

            if stock < 0:
                messages.error(request,"Variant stock cannot be negative.")
                return render(request,"adminside/product_edit.html",
                    {
                        "product": product,
                        "categories": categories,
                        "variants": variants,
                        "images": images,
                    }
                )

            if stock > 1000000:
                messages.error(request,"Variant stock cannot exceed 1,000,000.")
                return render(request,"adminside/product_edit.html",
                    {
                        "product": product,
                        "categories": categories,
                        "variants": variants,
                        "images": images,
                    }
                )

        for index in range(len(variant_colors)):

            variant_id = variant_ids[index]
            new_images = request.FILES.getlist(f"variant_images_{index}")

            if variant_id:
                variant = get_object_or_404(
                    product.variants,
                    id=variant_id)

                existing_count = ProductImage.objects.filter(product_variant=variant).count()

                

                total_count = existing_count + len(new_images)

            #     if total_count != 3:
            #         messages.error(request,f"Variant {index + 1} must have exactly 3 images.")
            #         return render(request,"adminside/product_edit.html",
            #         {
            #             "product": product,
            #             "categories": categories,
            #             "variants": variants,
            #             "images": images,
            #         })

            # else:
            

                # if len(new_images) != 3:
                #     messages.error(
                #     request,f"New variant {index + 1} must have exactly 3 images.")
                #     return render(request,"adminside/product_edit.html",
                #         {
                #         "product": product,
                #         "categories": categories,
                #         "variants": variants,
                #         "images": images,})

            for image in new_images:

                if image.content_type not in [
                    "image/jpeg",
                    "image/png",
                    "image/webp",]:
                    messages.error(request,"Only JPG, PNG, and WEBP images are allowed.")
                    return render(request,"adminside/product_edit.html",{
                        "product": product,
                        "categories": categories,
                        "variants": variants,
                        "images": images,})

                if image.size > 5 * 1024 * 1024:
                    messages.error(request,"Each image must be 5 MB or smaller.")
                    return render(request,"adminside/product_edit.html",{
                        "product": product,
                        "categories": categories,
                        "variants": variants,
                        "images": images,})

        product.name = name
        product.description = description
        product.regular_price = regular_price
        product.low_stock_threshold = low_stock_threshold
        product.category = category
        product.save()

        for index, (variant_id, color, size, price, stock) in enumerate(
                zip(
                    variant_ids,
                    variant_colors,
                    variant_sizes,
                    variant_prices,
                    variant_stocks)):

            if variant_id:

                variant = get_object_or_404(
                    product.variants,
                    id=variant_id)

                variant.color = color.strip()
                variant.size = size.strip()
                variant.price = Decimal(price)
                variant.stock_quantity = int(stock)
                variant.save()

            else:

                variant = ProductVariant.objects.create(
                    product=product,
                    color=color.strip(),
                    size=size.strip(),
                    price=Decimal(price),
                    stock_quantity=int(stock))

            new_images = request.FILES.getlist(
                f"variant_images_{index}")

            if not new_images:
                continue

            last_image = ProductImage.objects.filter(
                product_variant=variant
            ).order_by("-sort_order").first()

            sort_order = last_image.sort_order + 1 if last_image else 0

            has_primary = ProductImage.objects.filter(
                product_variant=variant,
                is_primary=True).exists()

            for image_index, image in enumerate(new_images):

                file_path = (
                    f"products/{product.id}/variants/"
                    f"{variant.id}/{image.name}"
                )

                saved_path = default_storage.save(
                    file_path,
                    image)

                ProductImage.objects.create(
                    product_variant=variant,
                    image_url=saved_path,
                    is_primary=(
                        not has_primary and image_index == 0
                    ),
                    sort_order=sort_order
                )

                sort_order += 1

        messages.success(request, "Product updated successfully.")
        return redirect("admin_product_list")
    
    return render(request,"adminside/product_edit.html", { "product": product, "categories": categories, "variants": variants, "images": images, } )