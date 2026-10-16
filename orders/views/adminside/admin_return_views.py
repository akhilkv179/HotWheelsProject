from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from orders.models import OrderItem, Return
from products.models import ProductVariant


RETURN_STATUSES = [
    "requested",
    "item_received",
    "inspection_approved",
    "inspection_rejected",
    "refund_processed",
]


@staff_member_required
def admin_return_list(request):
    returns = Return.objects.select_related(
        "user",
        "order_item",
        "order_item__order",
        "order_item__product_variant",
    ).order_by("-requested_at")

    return render(
        request,
        "adminside/admin_return_list.html",
        {
            "returns": returns,
            "return_statuses": RETURN_STATUSES,
        },
    )


@staff_member_required
@require_POST
def admin_update_return_status(request, return_id):
    new_status = request.POST.get("status", "").strip()
    internal_note = request.POST.get("internal_note", "").strip()

    if new_status not in RETURN_STATUSES:
        messages.error(request, "Invalid return status.")
        return redirect("admin_return_list")

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

    with transaction.atomic():
        return_request = get_object_or_404(
            Return.objects.select_for_update(),
            id=return_id,
        )

        if new_status == return_request.status:
            messages.info(
                request,
                "The return already has this status.",
            )
            return redirect("admin_return_list")

        if new_status not in allowed_transitions.get(
            return_request.status, []
        ):
            messages.error(
                request,
                f"Cannot change return status from "
                f"{return_request.status} to {new_status}.",
            )
            return redirect("admin_return_list")

        # Lock the exact order item to prevent concurrent
        # approvals from restoring its stock more than once.
        item = None

        if new_status == "inspection_approved":
            item = get_object_or_404(
                OrderItem.objects.select_for_update(),
                id=return_request.order_item_id,
            )

            if item.item_status != "active":
                messages.error(
                    request,
                    "This item has already been cancelled or returned. "
                    "Stock was not changed.",
                )
                return redirect("admin_return_list")

            variant = get_object_or_404(
                ProductVariant.objects.select_for_update(),
                id=item.product_variant_id,
            )

            # Restore stock once, after inspection approval.
            variant.stock_quantity += item.quantity
            variant.save(
                update_fields=["stock_quantity", "updated_at"]
            )

            item.item_status = "returned"
            item.save(update_fields=["item_status"])

        # Update return status and admin note.
        return_request.status = new_status
        return_request.internal_note = internal_note

        # processed_at records the latest status-processing action.
        return_request.processed_at = timezone.now()

        return_request.save(
            update_fields=[
                "status",
                "internal_note",
                "processed_at",
                "updated_at",
            ]
        )

    if new_status == "inspection_approved":
        messages.success(
            request,
            "Return approved and stock updated successfully.",
        )
    elif new_status == "inspection_rejected":
        messages.success(
            request,
            "Return rejected. Stock was not changed.",
        )
    elif new_status == "refund_processed":
        messages.success(
            request,
            "Return status updated to refund processed. "
            "Verify the actual refund separately.",
        )
    else:
        messages.success(
            request,
            "Return status updated successfully.",
        )

    return redirect("admin_return_list")
