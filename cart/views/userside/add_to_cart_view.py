from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse

from cart.models import Cart, CartItem
from products.models import ProductVariant
from wishlist.models import WishlistItem


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Add a product variant to the customer's cart or increment its quantity.
@login_required
def add_to_cart(request, variant_id):

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

    variant = get_object_or_404(
        ProductVariant.objects.select_related(
            "product", "product__category"
        ),
        id=variant_id
    )

    if not variant.is_active:
        error_message = "This product variant is unavailable."

        if wants_json(request):
            return JsonResponse(
                {"success": False, "message": error_message},
                status=400
            )

        messages.error(request, error_message)
        return redirect("user_product_list")

    if not variant.product.is_active:
        error_message = "This product is unavailable."

        if wants_json(request):
            return JsonResponse(
                {"success": False, "message": error_message},
                status=400
            )

        messages.error(request, error_message)
        return redirect("user_product_list")

    if not variant.product.category.is_active:
        error_message = "This product is unavailable."

        if wants_json(request):
            return JsonResponse(
                {"success": False, "message": error_message},
                status=400
            )

        messages.error(request, error_message)
        return redirect("user_product_list")

    if variant.stock_quantity <= 0:
        error_message = "This product is out of stock."

        if wants_json(request):
            return JsonResponse(
                {"success": False, "message": error_message},
                status=409
            )

        messages.error(request, error_message)
        return redirect(
            "user_product_details",
            product_id=variant.product.id
        )

    cart, created = Cart.objects.get_or_create(
        user=request.user
    )

    cart_item = CartItem.objects.filter(
        cart=cart,
        product_variant=variant
    ).first()

    MAX_QUANTITY = 5

    if cart_item:
        new_quantity = cart_item.quantity + 1

        if new_quantity > MAX_QUANTITY:
            error_message = (
                f"You can add a maximum of {MAX_QUANTITY} items."
            )

            if wants_json(request):
                return JsonResponse(
                    {"success": False, "message": error_message},
                    status=409
                )

            messages.error(request, error_message)
            return redirect(
                "user_product_details",
                product_id=variant.product.id
            )

        if new_quantity > variant.stock_quantity:
            error_message = (
                "You cannot add more than the available stock."
            )

            if wants_json(request):
                return JsonResponse(
                    {"success": False, "message": error_message},
                    status=409
                )

            messages.error(request, error_message)
            return redirect(
                "user_product_details",
                product_id=variant.product.id
            )

        cart_item.quantity = new_quantity
        cart_item.save()

    else:
        CartItem.objects.create(
            cart=cart,
            product_variant=variant,
            quantity=1,
            unit_price=variant.price
        )

    WishlistItem.objects.filter(
        wishlist__user=request.user,
        product_variant=variant
    ).delete()

    success_message = "Product added to cart."

    if wants_json(request):
        return JsonResponse(
            {
                "success": True,
                "message": success_message,
                "cart_url": reverse("cart_list"),
                "product_url": reverse(
                    "user_product_details",
                    kwargs={"product_id": variant.product.id}
                )
            },
            status=200
        )

    messages.success(request, success_message)

    return redirect(
        "user_product_details",
        product_id=variant.product.id
    )