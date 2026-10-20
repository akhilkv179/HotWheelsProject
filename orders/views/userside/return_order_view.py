
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone

from orders.models import OrderItem, Return


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Submit a return request for a delivered order item with a reason.
@login_required
def request_return(request, order_number, item_id):
    # Only allow POST requests to submit a return request.
    if request.method != "POST":
        if wants_json(request):
            return JsonResponse(
                {"error": "Only POST requests are allowed."},
                status=405,
            )
        return HttpResponseNotAllowed(["POST"])

    # Read the return reason and additional details from the form.
    reason = request.POST.get("reason", "").strip()
    description = request.POST.get("description", "").strip()
    user_note = request.POST.get("user_add_note", "").strip()

    with transaction.atomic():
        # Find and lock the order item belonging to the logged-in user.
        item = get_object_or_404(
            OrderItem.objects.select_for_update().select_related("order"),
            id=item_id,
            order__order_number=order_number,
            order__user=request.user,
        )

        # Returns are allowed only after an order has been delivered.
        if item.order.status != "delivered":
            error_message = "Only delivered orders can be returned."

            if wants_json(request):
                return JsonResponse({"error": error_message}, status=400)

            messages.error(request, error_message)
            return redirect(
                "user_order_detail",
                order_number=order_number,
            )

        # Prevent returns for cancelled or already-processed items.
        if item.item_status != "active":
            error_message = (
                "Cancelled or already-returned items cannot be returned."
            )

            if wants_json(request):
                return JsonResponse({"error": error_message}, status=400)

            messages.error(request, error_message)
            return redirect(
                "user_order_detail",
                order_number=order_number,
            )

        # Validate that the customer has provided a return reason.
        if not reason:
            error_message = "Return reason is required."

            if wants_json(request):
                return JsonResponse({"error": error_message}, status=400)

            messages.error(request, error_message)
            return redirect(
                "user_order_detail",
                order_number=order_number,
            )

        # Validate that the customer has described the return reason.
        if not description:
            error_message = "Please describe the return reason."

            if wants_json(request):
                return JsonResponse({"error": error_message}, status=400)

            messages.error(request, error_message)
            return redirect(
                "user_order_detail",
                order_number=order_number,
            )

        # Check whether a return request already exists for this item.
        existing_return = Return.objects.filter(
            order_item=item,
            status__in=[
                "requested",
                "item_received",
                "inspection_approved",
                "inspection_rejected",
                "refund_processed",
            ],
        ).exists()

        if existing_return:
            error_message = (
                "A return request already exists for this item."
            )

            if wants_json(request):
                return JsonResponse({"error": error_message}, status=400)

            messages.error(request, error_message)
            return redirect(
                "user_order_detail",
                order_number=order_number,
            )

        # Create the return request with its initial status.
        return_request = Return.objects.create(
            order_item=item,
            user=request.user,
            reason=reason,
            description=description,
            user_add_note=user_note,
            internal_note="",
            status="requested",
            requested_at=timezone.now(),
        )

    # Return the created request details to JSON clients.
    if wants_json(request):
        return JsonResponse(
            {
                "message": "Your return request has been submitted.",
                "return_id": return_request.id,
                "order_number": order_number,
                "order_item_id": item.id,
                "reason": return_request.reason,
                "description": return_request.description,
                "status": return_request.status,
                "requested_at": return_request.requested_at.isoformat(),
            },
            status=201,
        )

    # Preserve the existing success message and redirect for HTML clients.
    messages.success(
        request,
        "Your return request has been submitted.",
    )

    return redirect(
        "user_order_detail",
        order_number=order_number,
    )
