
from decimal import Decimal, ROUND_HALF_UP

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from coupons.models import CouponUsage
from orders.models import OrderItem, Return
from payments.models import Refund
from products.models import ProductVariant
from wallet.services.refund_service import credit_wallet_refund


ZERO = Decimal("0.00")
CENT = Decimal("0.01")


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


# Allocate the original coupon discount across all items proportionally.
def get_coupon_discount_allocations(order, items):
    allocations = {item.pk: ZERO for item in items}

    if not order.coupon_id or not items:
        return allocations

    # Use the recorded original discount so previous cancellations
    # do not change how the coupon discount is allocated.
    usage = CouponUsage.objects.filter(
        order=order,
        coupon_id=order.coupon_id,
    ).order_by("pk").first()

    if usage:
        coupon_discount = usage.discount_amount or ZERO
    else:
        # Compatibility fallback for older coupon orders without
        # a CouponUsage record.
        product_discount_total = sum(
            (item.discount_amount or ZERO for item in items),
            ZERO,
        )

        coupon_discount = max(
            (order.discount_amount or ZERO) - product_discount_total,
            ZERO,
        )

    # Item totals already include product-offer discounts.
    weights = {
        item.pk: max(item.total_price or ZERO, ZERO)
        for item in items
    }

    eligible_total = sum(weights.values(), ZERO)

    if coupon_discount <= ZERO or eligible_total <= ZERO:
        return allocations

    # Do not allocate more coupon discount than the eligible item totals.
    coupon_discount = min(coupon_discount, eligible_total)

    eligible_items = [
        item for item in items
        if weights[item.pk] > ZERO
    ]

    remaining_discount = coupon_discount

    # Round each proportional allocation to cents, assigning any
    # remaining cents to the final eligible item.
    for item in eligible_items[:-1]:
        share = (
            coupon_discount * weights[item.pk] / eligible_total
        ).quantize(CENT, rounding=ROUND_HALF_UP)

        share = min(max(share, ZERO), remaining_discount)

        allocations[item.pk] = share
        remaining_discount -= share

    if eligible_items:
        allocations[eligible_items[-1].pk] = remaining_discount

    return allocations




# Display all customer return requests with pagination.
@staff_member_required(login_url="/d/admin_login/")
def admin_return_list(request):
    if request.method != "GET":
        if wants_json(request):
            return JsonResponse(
                {"error": "Method not allowed."},
                status=405,
            )
        return HttpResponseNotAllowed(["GET"])

    returns = Return.objects.select_related(
        "user",
        "order_item",
        "order_item__order",
        "order_item__product_variant",
    ).order_by("-requested_at")

    # Calculate the coupon-adjusted price for each returned item.
    return_items_by_order = {}

    for return_request in returns:
        item = return_request.order_item
        order = item.order

        if order.pk not in return_items_by_order:
            return_items_by_order[order.pk] = list(
                OrderItem.objects.filter(order_id=order.pk).order_by("pk")
            )

    coupon_allocations_by_order = {}

    for return_request in returns:
        item = return_request.order_item
        order = item.order

        if order.pk not in coupon_allocations_by_order:
            coupon_allocations_by_order[order.pk] = (
                get_coupon_discount_allocations(
                    order,
                    return_items_by_order[order.pk],
                )
            )

    paginator = Paginator(returns, 5)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    def get_paid_item_price(return_request):
        item = return_request.order_item
        coupon_discount = coupon_allocations_by_order[
            item.order_id
        ].get(item.pk, ZERO)

        return max(
            (item.total_price or ZERO) - coupon_discount,
            ZERO,
        ).quantize(CENT, rounding=ROUND_HALF_UP)

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
                        "original_item_price": str(
                            return_request.order_item.total_price or ZERO
                        ),
                        "coupon_discount": str(
                            coupon_allocations_by_order[
                                return_request.order_item.order_id
                            ].get(
                                return_request.order_item_id,
                                ZERO,
                            )
                        ),
                        "paid_item_price": str(
                            get_paid_item_price(return_request)
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
                    for return_request in page_obj
                ],
                "return_statuses": RETURN_STATUSES,
                "total_returns": paginator.count,
                "current_page": page_obj.number,
                "total_pages": paginator.num_pages,
                "has_next": page_obj.has_next(),
                "has_previous": page_obj.has_previous(),
                "next_page": (
                    page_obj.next_page_number()
                    if page_obj.has_next()
                    else None
                ),
                "previous_page": (
                    page_obj.previous_page_number()
                    if page_obj.has_previous()
                    else None
                ),
            },
            status=200,
        )

    # Attach the calculated prices for use in the HTML template.
    for return_request in page_obj:
        item = return_request.order_item
        return_request.original_item_price = item.total_price or ZERO
        return_request.coupon_discount = (
            coupon_allocations_by_order[item.order_id].get(
                item.pk, ZERO
            )
        )
        return_request.paid_item_price = get_paid_item_price(
            return_request
        )

    return render(
        request,
        "adminside/admin_return_list.html",
        {
            "returns": page_obj,
            "return_statuses": RETURN_STATUSES,
            "page_obj": page_obj,
            "paginator": paginator,
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

        # Credit the wallet when the administrator processes a refund.
        if new_status == "refund_processed":
            # Prevent the same return from being refunded twice.
            if Refund.objects.filter(
                return_request=return_request
            ).exists():
                error_message = "This return has already been refunded."

                if wants_json(request):
                    return JsonResponse(
                        {"error": error_message},
                        status=400,
                    )

                messages.error(request, error_message)
                return redirect("admin_return_list")

            # Lock the order item associated with this return.
            return_item = get_object_or_404(
                OrderItem.objects.select_for_update().select_related(
                    "order"
                ),
                id=return_request.order_item_id,
            )

            # Allocate the original coupon discount across all order items.
            order_items = list(
                OrderItem.objects.select_for_update()
                .filter(order_id=return_item.order_id)
                .order_by("pk")
            )

            coupon_allocations = get_coupon_discount_allocations(
                return_item.order,
                order_items,
            )

            coupon_discount_for_item = coupon_allocations.get(
                return_item.pk,
                ZERO,
            )

            # total_price already includes product-offer discounts.
            # Subtract this item's allocated coupon discount as well.
            refund_amount = (
                (return_item.total_price or ZERO)
                - coupon_discount_for_item
            ).quantize(CENT, rounding=ROUND_HALF_UP)

            if refund_amount <= ZERO:
                error_message = (
                    "The refund amount must be greater than zero."
                )

                if wants_json(request):
                    return JsonResponse(
                        {"error": error_message},
                        status=400,
                    )

                messages.error(request, error_message)
                return redirect("admin_return_list")

            # Credit the refund using the shared wallet transaction service.
            try:
                wallet_transaction = credit_wallet_refund(
                    user=return_request.user,
                    amount=refund_amount,
                    transaction_id=(
                        f"RETURN-REFUND-{return_request.pk}"
                    ),
                    reference_id=f"RETURN-{return_request.pk}",
                )
            except ValidationError as error:
                error_message = (
                    error.messages[0]
                    if error.messages
                    else "The wallet refund could not be processed."
                )

                if wants_json(request):
                    return JsonResponse(
                        {"error": error_message},
                        status=400,
                    )

                messages.error(request, error_message)
                return redirect("admin_return_list")

            # Save the refund record in the same database transaction.
            Refund.objects.create(
                return_request=return_request,
                wallet_transaction=wallet_transaction,
                amount=refund_amount,
                status="processed",
                processed_at=timezone.now(),
            )

        # Save the new return status and administrator's note.
        return_request.status = new_status
        return_request.internal_note = internal_note
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
            "Refund credited to the customer's wallet successfully."
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
