from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render, redirect

from cart.models import Cart


MAX_QUANTITY = 5


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Validate cart items and stock before proceeding to order checkout.
@login_required
def checkout(request):

    if request.method != "GET":
        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Only GET requests are allowed."
                },
                status=405
            )

        return HttpResponseNotAllowed(["GET"])

    cart = Cart.objects.filter(
        user=request.user
    ).first()

    if not cart:
        error_message = "Your cart is empty."

        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": error_message,
                    "redirect_url": redirect("cart_list").url
                },
                status=400
            )

        messages.error(request, error_message)
        return redirect("cart_list")

    cart_items = cart.items.select_related(
        "product_variant",
        "product_variant__product",
        "product_variant__product__category"
    )

    if not cart_items.exists():
        error_message = "Your cart is empty."

        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": error_message,
                    "redirect_url": redirect("cart_list").url
                },
                status=400
            )

        messages.error(request, error_message)
        return redirect("cart_list")

    for item in cart_items:

        variant = item.product_variant
        product = variant.product
        category = product.category

        if (
            not variant.is_active
            or not product.is_active
            or not category.is_active
        ):
            error_message = (
                "Your cart contains an unavailable product."
            )

            if wants_json(request):
                return JsonResponse(
                    {
                        "success": False,
                        "message": error_message,
                        "redirect_url": redirect("cart_list").url
                    },
                    status=409
                )

            messages.error(request, error_message)
            return redirect("cart_list")

        if variant.stock_quantity <= 0:
            error_message = (
                "Your cart contains an out-of-stock product."
            )

            if wants_json(request):
                return JsonResponse(
                    {
                        "success": False,
                        "message": error_message,
                        "redirect_url": redirect("cart_list").url
                    },
                    status=409
                )

            messages.error(request, error_message)
            return redirect("cart_list")

        if item.quantity > MAX_QUANTITY:
            error_message = (
                f"You can add a maximum of {MAX_QUANTITY} items."
            )

            if wants_json(request):
                return JsonResponse(
                    {
                        "success": False,
                        "message": error_message,
                        "redirect_url": redirect("cart_list").url
                    },
                    status=409
                )

            messages.error(request, error_message)
            return redirect("cart_list")

        if item.quantity > variant.stock_quantity:
            error_message = (
                "The quantity of a product in your cart exceeds available stock."
            )

            if wants_json(request):
                return JsonResponse(
                    {
                        "success": False,
                        "message": error_message,
                        "redirect_url": redirect("cart_list").url
                    },
                    status=409
                )

            messages.error(request, error_message)
            return redirect("cart_list")

    if wants_json(request):
        return JsonResponse(
            {
                "success": True,
                "message": "Your cart is valid for checkout.",
                "checkout_available": True
            },
            status=200
        )

    return render(
        request,
        "userside/checkout.html",
        {
            "cart": cart,
            "cart_items": cart_items,
        }
    )