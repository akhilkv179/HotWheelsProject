from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect

from cart.models import CartItem


MAX_QUANTITY = 5


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Increase or decrease the quantity of a cart item within available stock limits.
@login_required
def update_cart_quantity(request, item_id, action):

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

    if action not in ["increase", "decrease"]:
        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Invalid quantity update action."
                },
                status=400
            )

        messages.error(request, "Invalid quantity update action.")
        return redirect("cart_list")

    cart_item = get_object_or_404(
        CartItem.objects.select_related(
            "product_variant",
            "product_variant__product",
            "product_variant__product__category"
        ),
        id=item_id,
        cart__user=request.user
    )

    variant = cart_item.product_variant
    product = variant.product
    category = product.category

    if (
        not variant.is_active
        or not product.is_active
        or not category.is_active
        or variant.stock_quantity <= 0
    ):
        error_message = "This product is currently unavailable."

        if wants_json(request):
            return JsonResponse(
                {"success": False, "message": error_message},
                status=409
            )

        messages.error(request, error_message)
        return redirect("cart_list")

    if action == "increase":

        if cart_item.quantity >= MAX_QUANTITY:
            error_message = (
                f"You can add a maximum of {MAX_QUANTITY} items."
            )

            if wants_json(request):
                return JsonResponse(
                    {"success": False, "message": error_message},
                    status=409
                )

            messages.error(request, error_message)
            return redirect("cart_list")

        if cart_item.quantity >= variant.stock_quantity:
            error_message = (
                "You cannot add more than the available stock."
            )

            if wants_json(request):
                return JsonResponse(
                    {"success": False, "message": error_message},
                    status=409
                )

            messages.error(request, error_message)
            return redirect("cart_list")

        cart_item.quantity += 1
        cart_item.save(update_fields=["quantity"])

        success_message = "Cart quantity increased."

    else:  # action == "decrease"

        if cart_item.quantity <= 1:
            cart_item.delete()
            success_message = "Product removed from cart."

            if wants_json(request):
                return JsonResponse(
                    {
                        "success": True,
                        "message": success_message,
                        "item_id": item_id,
                        "removed": True
                    },
                    status=200
                )

            messages.success(request, success_message)
            return redirect("cart_list")

        cart_item.quantity -= 1
        cart_item.save(update_fields=["quantity"])

        success_message = "Cart quantity decreased."

    if wants_json(request):
        return JsonResponse(
            {
                "success": True,
                "message": success_message,
                "item_id": cart_item.id,
                "quantity": cart_item.quantity,
                "removed": False
            },
            status=200
        )

    return redirect("cart_list")