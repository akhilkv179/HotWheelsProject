from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect

from cart.models import CartItem


# Remove a specific item from the logged-in user's shopping cart.
@login_required
def remove_from_cart(request, item_id):

    if request.method != "POST":
        if "application/json" in request.headers.get("Accept", ""):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Only POST requests are allowed."
                },
                status=405
            )

        return HttpResponseNotAllowed(["POST"])

    cart_item = get_object_or_404(
        CartItem,
        id=item_id,
        cart__user=request.user
    )

    cart_item.delete()

    success_message = "Product removed from cart."

    if "application/json" in request.headers.get("Accept", ""):
        return JsonResponse(
            {
                "success": True,
                "message": success_message,
                "item_id": item_id
            },
            status=200
        )

    messages.success(request, success_message)
    return redirect("cart_list")