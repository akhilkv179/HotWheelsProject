
from decimal import Decimal, ROUND_HALF_UP

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect

from coupons.models import CouponUsage
from orders.models import Order, OrderItem, OrderStatusHistory
from products.models import ProductVariant
from wallet.services.refund_service import credit_wallet_refund


ZERO = Decimal("0.00")
CENT = Decimal("0.01")


def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


def get_coupon_discount_allocations(order, items):
    """Allocate the original coupon discount proportionally across order items."""
    allocations = {item.pk: ZERO for item in items}

    if not order.coupon_id or not items:
        return allocations

    usage = CouponUsage.objects.filter(
        order=order,
        coupon_id=order.coupon_id,
    ).order_by("pk").first()

    if usage:
        coupon_discount = usage.discount_amount or ZERO
    else:
        product_discount_total = sum(
            (item.discount_amount or ZERO for item in items),
            ZERO,
        )
        coupon_discount = max(
            (order.discount_amount or ZERO) - product_discount_total,
            ZERO,
        )

    weights = {
        item.pk: max(item.total_price or ZERO, ZERO)
        for item in items
    }
    eligible_total = sum(weights.values(), ZERO)

    if coupon_discount <= ZERO or eligible_total <= ZERO:
        return allocations

    coupon_discount = min(coupon_discount, eligible_total)

    eligible_items = [
        item for item in items if weights[item.pk] > ZERO
    ]
    remaining_discount = coupon_discount

    # Assign any rounding remainder to the final eligible item.
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


@login_required
def cancel_order(request, order_number, item_id):
    if request.method != "POST":
        if wants_json(request):
            return JsonResponse(
                {"error": "Only POST requests are allowed."},
                status=405,
            )
        return HttpResponseNotAllowed(["POST"])

    # Accept either field name to support existing frontend payloads.
    cancellation_reason = (
        request.POST.get("cancellation_reason")
        or request.POST.get("reason", "")
    ).strip()

    if not cancellation_reason:
        error_message = "Please provide a reason for cancelling this item."

        if wants_json(request):
            return JsonResponse({"error": error_message}, status=400)

        messages.error(request, error_message)
        return redirect(
            "user_order_detail",
            order_number=order_number,
        )

    try:
        with transaction.atomic():
            order = get_object_or_404(
                Order.objects.select_for_update(),
                order_number=order_number,
                user=request.user,
            )

            if order.status not in ["pending", "confirmed"]:
                error_message = "This order can no longer be cancelled."

                if wants_json(request):
                    return JsonResponse(
                        {"error": error_message},
                        status=400,
                    )

                messages.error(request, error_message)
                return redirect(
                    "user_order_detail",
                    order_number=order.order_number,
                )

            all_items = list(
                order.items.select_for_update().order_by("pk")
            )

            item = next(
                (
                    order_item
                    for order_item in all_items
                    if order_item.pk == item_id
                ),
                None,
            )

            if item is None:
                error_message = "Order item not found."

                if wants_json(request):
                    return JsonResponse(
                        {"error": error_message},
                        status=404,
                    )

                messages.error(request, error_message)
                return redirect(
                    "user_order_detail",
                    order_number=order.order_number,
                )

            if item.item_status != "active":
                error_message = "This item can no longer be cancelled."

                if wants_json(request):
                    return JsonResponse(
                        {"error": error_message},
                        status=400,
                    )

                messages.error(request, error_message)
                return redirect(
                    "user_order_detail",
                    order_number=order.order_number,
                )

            previous_total = order.total_amount or ZERO

            # Calculate coupon allocations before changing the item status.
            coupon_allocations = get_coupon_discount_allocations(
                order,
                all_items,
            )

            variant = get_object_or_404(
                ProductVariant.objects.select_for_update(),
                id=item.product_variant_id,
            )

            # Restore stock and save the cancellation reason together.
            variant.stock_quantity += item.quantity
            variant.save(
                update_fields=["stock_quantity", "updated_at"]
            )

            item.item_status = "cancelled"
            item.cancellation_reason = cancellation_reason
            item.save(
                update_fields=[
                    "item_status",
                    "cancellation_reason",
                ]
            )

            remaining_items = [
                order_item
                for order_item in all_items
                if order_item.item_status == "active"
            ]

            remaining_subtotal = sum(
                (
                    remaining_item.unit_price * remaining_item.quantity
                    for remaining_item in remaining_items
                ),
                ZERO,
            )

            remaining_product_discount = sum(
                (
                    remaining_item.discount_amount or ZERO
                    for remaining_item in remaining_items
                ),
                ZERO,
            )

            remaining_coupon_discount = sum(
                (
                    coupon_allocations.get(remaining_item.pk, ZERO)
                    for remaining_item in remaining_items
                ),
                ZERO,
            )

            if not remaining_items:
                order.status = "cancelled"
                order.subtotal = ZERO
                order.discount_amount = ZERO
                order.shipping_amount = ZERO
                order.total_amount = ZERO

                OrderStatusHistory.objects.create(
                    order=order,
                    status="cancelled",
                )

                message = "All items have been cancelled."

            else:
                order.subtotal = remaining_subtotal
                order.discount_amount = (
                    remaining_product_discount
                    + remaining_coupon_discount
                )

                # Preserve the existing shipping policy for partial cancellation.
                order.total_amount = (
                    order.subtotal
                    - order.discount_amount
                    + order.shipping_amount
                )

                message = "The selected item has been cancelled."

            refund_amount = max(
                previous_total - order.total_amount,
                ZERO,
            ).quantize(CENT, rounding=ROUND_HALF_UP)

            paid_online = (
                order.delivery_method.strip().lower()
                in ("wallet", "razorpay")
                and order.payments.filter(status="paid").exists()
            )

            if paid_online and refund_amount > ZERO:
                credit_wallet_refund(
                    user=request.user,
                    amount=refund_amount,
                    transaction_id=f"CANCEL-{order.pk}-{item.pk}",
                    reference_id=order.order_number,
                )

                message += " The refund has been credited to your wallet."

            order.save(
                update_fields=[
                    "status",
                    "subtotal",
                    "discount_amount",
                    "shipping_amount",
                    "total_amount",
                    "updated_at",
                ]
            )

    except ValidationError as error:
        error_message = (
            error.messages[0]
            if error.messages
            else "The refund could not be processed."
        )

        if wants_json(request):
            return JsonResponse(
                {"error": error_message},
                status=400,
            )

        messages.error(request, error_message)
        return redirect(
            "user_order_detail",
            order_number=order_number,
        )

    if wants_json(request):
        return JsonResponse(
            {
                "message": message,
                "order_number": order.order_number,
                "order_status": order.status,
                "item_id": item.id,
                "item_status": item.item_status,
                "cancellation_reason": item.cancellation_reason,
                "subtotal": str(order.subtotal),
                "discount_amount": str(order.discount_amount),
                "shipping_amount": str(order.shipping_amount),
                "total_amount": str(order.total_amount),
            },
            status=200,
        )

    messages.success(request, message)

    return redirect(
        "user_order_detail",
        order_number=order.order_number,
    )
