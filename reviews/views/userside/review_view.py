
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from orders.models import OrderItem
from reviews.models import Review


def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


@login_required
@require_POST
def submit_review(request, order_number, item_id):
    order_item = get_object_or_404(
        OrderItem.objects.select_related("order"),
        id=item_id,
        order__order_number=order_number,
        order__user=request.user,
    )

    if order_item.order.status.lower() not in {
        "delivered",
        "completed",
    }:
        error_message = "You can review an item only after delivery."

        if wants_json(request):
            return JsonResponse({"error": error_message}, status=400)

        messages.error(request, error_message)
        return redirect(
            "user_order_detail",
            order_number=order_number,
        )

    if order_item.item_status != "active":
        error_message = "Cancelled or returned items cannot be reviewed."

        if wants_json(request):
            return JsonResponse({"error": error_message}, status=400)

        messages.error(request, error_message)
        return redirect(
            "user_order_detail",
            order_number=order_number,
        )

    rating_value = request.POST.get("rating", "").strip()
    review_text = request.POST.get("review_text", "").strip()

    try:
        rating = int(rating_value)
    except (TypeError, ValueError):
        rating = 0

    if rating not in range(1, 6):
        error_message = "Please select a rating from 1 to 5 stars."

        if wants_json(request):
            return JsonResponse({"error": error_message}, status=400)

        messages.error(request, error_message)
        return redirect(
            "user_order_detail",
            order_number=order_number,
        )

    if not review_text:
        error_message = "Please enter your review."

        if wants_json(request):
            return JsonResponse({"error": error_message}, status=400)

        messages.error(request, error_message)
        return redirect(
            "user_order_detail",
            order_number=order_number,
        )

    if len(review_text) > 1000:
        error_message = "Your review cannot exceed 1000 characters."

        if wants_json(request):
            return JsonResponse({"error": error_message}, status=400)

        messages.error(request, error_message)
        return redirect(
            "user_order_detail",
            order_number=order_number,
        )

    if Review.objects.filter(order_item=order_item).exists():
        error_message = "You have already reviewed this item."

        if wants_json(request):
            return JsonResponse({"error": error_message}, status=409)

        messages.error(request, error_message)
        return redirect(
            "user_order_detail",
            order_number=order_number,
        )

    try:
        with transaction.atomic():
            review = Review.objects.create(
                order_item=order_item,
                rating=rating,
                review_text=review_text,
            )
    except IntegrityError:
        error_message = "A review could not be created. Please try again."

        if wants_json(request):
            return JsonResponse({"error": error_message}, status=409)

        messages.error(request, error_message)
        return redirect(
            "user_order_detail",
            order_number=order_number,
        )

    if wants_json(request):
        return JsonResponse(
            {
                "message": "Review submitted successfully.",
                "review": {
                    "id": review.id,
                    "order_item_id": order_item.id,
                    "rating": review.rating,
                    "review_text": review.review_text,
                    "created_at": review.created_at.isoformat(),
                },
            },
            status=201,
        )

    messages.success(request, "Your review was submitted successfully.")
    return redirect(
        "user_order_detail",
        order_number=order_number,
    )


@login_required
@require_POST
def delete_review(request, review_id):
    review = get_object_or_404(
        Review.objects.select_related("order_item__order"),
        id=review_id,
        order_item__order__user=request.user,
    )

    review.delete()

    return JsonResponse(
        {
            "message": "Your review has been deleted successfully."
        },
        status=200,
    )