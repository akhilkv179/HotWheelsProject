
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from orders.models import OrderItem, Return
from products.models import ProductVariant


RETURN_STATUSES = [
    "requested",
    "item_received",
    "inspection_approved",
    "inspection_rejected",
    "refund_processed",
]


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Display all customer return requests for administrator review.
@staff_member_required(login_url="/d/admin_login/")
def admin_return_list(request):
    # Allow only GET requests to view return requests.
    if request.method != "GET":
        if wants_json(request):
            return JsonResponse(
                {"error": "Method not allowed."},
                status=405,
            )
        return HttpResponseNotAllowed(["GET"])

    # Retrieve return requests with their related order and product information.
    returns = Return.objects.select_related(
        "user",
        "order_item",
        "order_item__order",
        "order_item__product_variant",
    ).order_by("-requested_at")

    # Return return-request information as JSON when requested.
    if wants_json(request):
        return JsonResponse(
            {
                "returns": [
                    {
                        "id": return_request.id,
                        "username": return_request.user.username,
                        "order_number": (
                            return_request.order_item.order.order_number
                        ),
                        "product_variant_id": (
                            return_request.order_item.product_variant_id
                        ),
                        "status": return_request.status,
                        "internal_note": return_request.internal_note,
                        "requested_at": (
                            return_request.requested_at.isoformat()
                            if return_request.requested_at
                            else None
                        ),
                        "processed_at": (
                            return_request.processed_at.isoformat()
                            if return_request.processed_at
                            else None
                        ),
                    }
                    for return_request in returns
                ],
                "return_statuses": RETURN_STATUSES,
                "total_returns": returns.count(),
            },
            status=200,
        )

    # Render the normal HTML return-request list.
    return render(
        request,
        "adminside/admin_return_list.html",
        {
            "returns": returns,
            "return_statuses": RETURN_STATUSES,
        },
        status=200,
    )


# Update a return request through receipt, inspection, and refund processing.
@staff_member_required(login_url="/d/admin_login/")
def admin_update_return_status(request, return_id):
    # Allow return status changes only through POST requests.
    if request.method != "POST":
        if wants_json(request):
            return JsonResponse(
                {"error": "Method not allowed."},
                status=405,
            )
        return HttpResponseNotAllowed(["POST"])

    # Read the requested status and administrator's internal note.
    new_status = request.POST.get("status", "").strip()
    internal_note = request.POST.get("internal_note", "").strip()

    # Reject unsupported return statuses.
    if new_status not in RETURN_STATUSES:
        if wants_json(request):
            return JsonResponse(
                {"error": "Invalid return status."},
                status=400,
            )

        messages.error(request, "Invalid return status.")
        return redirect("admin_return_list")

    # Define the permitted return status transitions.
    allowed_transitions = {
        "requested": ["item_received"],
        "item_received": [
            "inspection_approved",
            "inspection_rejected",
        ],
        "inspection_approved": ["refund_processed"],
        "inspection_rejected": [],
        "refund_processed": [],
    }

    # Lock the return request while processing its status change.
    with transaction.atomic():
        return_request = get_object_or_404(
            Return.objects.select_for_update(),
            id=return_id,
        )

        # Avoid processing a status that is already set.
        if new_status == return_request.status:
            if wants_json(request):
                return JsonResponse(
                    {
                        "message": "The return already has this status.",
                        "return_id": return_request.id,
                        "status": return_request.status,
                    },
                    status=200,
                )

            messages.info(
                request,
                "The return already has this status.",
            )
            return redirect("admin_return_list")

        # Reject status changes that violate the return workflow.
        if new_status not in allowed_transitions.get(
            return_request.status, []
        ):
            error_message = (
                f"Cannot change return status from "
                f"{return_request.status} to {new_status}."
            )

            if wants_json(request):
                return JsonResponse(
                    {"error": error_message},
                    status=400,
                )

            messages.error(request, error_message)
            return redirect("admin_return_list")

        # Restore stock only after the returned item passes inspection.
        if new_status == "inspection_approved":
            # Lock the order item to prevent concurrent stock restoration.
            item = get_object_or_404(
                OrderItem.objects.select_for_update(),
                id=return_request.order_item_id,
            )

            # Prevent stock restoration if the item is no longer active.
            if item.item_status != "active":
                error_message = (
                    "This item has already been cancelled or returned. "
                    "Stock was not changed."
                )

                if wants_json(request):
                    return JsonResponse(
                        {"error": error_message},
                        status=400,
                    )

                messages.error(request, error_message)
                return redirect("admin_return_list")

            # Lock the product variant before changing its stock quantity.
            variant = get_object_or_404(
                ProductVariant.objects.select_for_update(),
                id=item.product_variant_id,
            )

            # Restore the returned quantity to available stock.
            variant.stock_quantity += item.quantity
            variant.save(
                update_fields=["stock_quantity", "updated_at"]
            )

            # Mark the order item as returned.
            item.item_status = "returned"
            item.save(update_fields=["item_status"])

        # Save the new return status and administrator's note.
        return_request.status = new_status
        return_request.internal_note = internal_note

        # Record when the latest status-processing action occurred.
        return_request.processed_at = timezone.now()

        return_request.save(
            update_fields=[
                "status",
                "internal_note",
                "processed_at",
                "updated_at",
            ]
        )

    # Prepare the appropriate success message after the transaction completes.
    if new_status == "inspection_approved":
        success_message = (
            "Return approved and stock updated successfully."
        )
    elif new_status == "inspection_rejected":
        success_message = (
            "Return rejected. Stock was not changed."
        )
    elif new_status == "refund_processed":
        success_message = (
            "Return status updated to refund processed. "
            "Verify the actual refund separately."
        )
    else:
        success_message = "Return status updated successfully."

    # Return the updated status as JSON when requested.
    if wants_json(request):
        return JsonResponse(
            {
                "message": success_message,
                "return_id": return_request.id,
                "status": return_request.status,
                "internal_note": return_request.internal_note,
                "processed_at": (
                    return_request.processed_at.isoformat()
                    if return_request.processed_at
                    else None
                ),
            },
            status=200,
        )

    # Display the success message and return to the HTML return list.
    messages.success(request, success_message)
    return redirect("admin_return_list")
