
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from orders.models import OrderItem, Return


@login_required
@require_POST
def request_return(request, order_number, item_id):
    reason = request.POST.get("reason", "").strip()
    description = request.POST.get("description", "").strip()
    user_note = request.POST.get("user_add_note", "").strip()

    with transaction.atomic():
        item = get_object_or_404(
            OrderItem.objects.select_for_update().select_related("order"),
            id=item_id,
            order__order_number=order_number,
            order__user=request.user,
        )

        if item.order.status != "delivered":
            messages.error(
                request,
                "Only delivered orders can be returned.",
            )
            return redirect(
                "user_order_detail",
                order_number=order_number,
            )

        if item.item_status != "active":
            messages.error(
                request,
                "Cancelled or already-returned items cannot be returned.",
            )
            return redirect(
                "user_order_detail",
                order_number=order_number,
            )

        if not reason:
            messages.error(
                request,
                "Return reason is required.",
            )
            return redirect(
                "user_order_detail",
                order_number=order_number,
            )

        if not description:
            messages.error(
                request,
                "Please describe the return reason.",
            )
            return redirect(
                "user_order_detail",
                order_number=order_number,
            )

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
            messages.error(
                request,
                "A return request already exists for this item.",
            )
            return redirect(
                "user_order_detail",
                order_number=order_number,
            )

        Return.objects.create(
            order_item=item,
            user=request.user,
            reason=reason,
            description=description,
            user_add_note=user_note,
            internal_note="",
            status="requested",
            requested_at=timezone.now(),
        )

    messages.success(
        request,
        "Your return request has been submitted.",
    )

    return redirect(
        "user_order_detail",
        order_number=order_number,
    )
