
import logging
from decimal import Decimal, ROUND_HALF_UP

import razorpay

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from orders.models import Order, OrderStatusHistory
from payments.models import Payment


logger = logging.getLogger(__name__)


@login_required
@require_POST
def expire_razorpay_payment(request, order_number):
    key_id = getattr(settings, "RAZORPAY_KEY_ID", "")
    key_secret = getattr(settings, "RAZORPAY_KEY_SECRET", "")

    if not key_id or not key_secret:
        return JsonResponse(
            {"error": "Razorpay is not configured correctly."},
            status=503,
        )

    order = Order.objects.filter(
        order_number=order_number,
        user=request.user,
        delivery_method="Razorpay",
    ).first()

    if order is None:
        return JsonResponse(
            {"error": "Order not found."},
            status=404,
        )

    payment = (
        Payment.objects.filter(
            order=order,
            payment_method="razorpay",
        )
        .exclude(razorpay_order_id="")
        .order_by("-created_at")
        .first()
    )

    if payment is None:
        return JsonResponse(
            {"error": "Payment record not found."},
            status=404,
        )

    if payment.status in ("paid", "success"):
        return JsonResponse(
            {
                "message": "Payment has already been completed.",
                "retry_allowed": False,
                "order_status": order.status,
            },
            status=409,
        )

    deadline = payment.retry_deadline

    if deadline is None:
        return JsonResponse(
            {
                "error": "No payment retry deadline is available.",
                "retry_allowed": False,
            },
            status=409,
        )

    if timezone.now() < deadline:
        return JsonResponse(
            {
                "message": "The retry period has not expired.",
                "retry_allowed": True,
                "retry_deadline": deadline.isoformat(),
            },
            status=409,
        )

    if order.status != "pending":
        return JsonResponse(
            {
                "message": "The order is no longer awaiting payment.",
                "retry_allowed": False,
                "order_status": order.status,
            },
            status=409,
        )

    if payment.status not in ("created", "failed"):
        return JsonResponse(
            {
                "error": "This payment cannot be expired.",
                "retry_allowed": False,
            },
            status=409,
        )

    # Verify every payment attempt associated with this Razorpay order.
    try:
        client = razorpay.Client(
            auth=(key_id, key_secret)
        )

        gateway_result = client.order.payments(
            payment.razorpay_order_id
        )

    except Exception:
        logger.exception(
            "Unable to verify Razorpay order %s before expiry.",
            payment.razorpay_order_id,
        )
        return JsonResponse(
            {
                "error": (
                    "Unable to verify payment status with Razorpay. "
                    "The order has not been cancelled."
                ),
            },
            status=502,
        )

    if (
        not isinstance(gateway_result, dict)
        or not isinstance(gateway_result.get("items"), list)
    ):
        logger.error(
            "Unexpected Razorpay payments response for order %s.",
            payment.razorpay_order_id,
        )
        return JsonResponse(
            {
                "error": (
                    "Razorpay returned an unexpected payment response. "
                    "The order has not been cancelled."
                ),
            },
            status=502,
        )

    gateway_payments = gateway_result["items"]

    # Without payment records to inspect, do not assume it is safe
    # to cancel the order.
    if not gateway_payments:
        return JsonResponse(
            {
                "error": (
                    "No gateway payment records were returned. "
                    "The order has not been cancelled."
                ),
                "retry_allowed": False,
            },
            status=409,
        )

    gateway_count = gateway_result.get("count")

    if (
        isinstance(gateway_count, int)
        and gateway_count > len(gateway_payments)
    ):
        return JsonResponse(
            {
                "error": (
                    "Not all gateway payment records were returned. "
                    "The order has not been cancelled."
                ),
                "retry_allowed": False,
            },
            status=409,
        )

    expected_amount = int(
        (payment.amount * Decimal("100")).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )

    for gateway_payment in gateway_payments:
        if not isinstance(gateway_payment, dict):
            return JsonResponse(
                {
                    "error": (
                        "Invalid gateway payment details. "
                        "The order has not been cancelled."
                    ),
                },
                status=502,
            )

        if (
            gateway_payment.get("order_id")
            != payment.razorpay_order_id
        ):
            return JsonResponse(
                {
                    "error": (
                        "Gateway payment details do not match this order. "
                        "The order has not been cancelled."
                    ),
                },
                status=409,
            )

        gateway_status = gateway_payment.get("status")

        # A captured payment must never be ignored because its amount
        # or currency differs from our local record.
        if gateway_status == "captured":
            logger.error(
                "Captured payment %s found during expiry of order %s.",
                gateway_payment.get("id"),
                order.order_number,
            )
            return JsonResponse(
                {
                    "error": (
                        "A captured payment was found. "
                        "The order has not been cancelled. "
                        "Payment reconciliation is required."
                    ),
                    "retry_allowed": False,
                },
                status=409,
            )

        # Unknown or non-final statuses are not safe to cancel.
        if gateway_status != "failed":
            return JsonResponse(
                {
                    "error": (
                        "A payment attempt is not confirmed as failed. "
                        "The order has not been cancelled."
                    ),
                    "gateway_payment_status": gateway_status,
                    "retry_allowed": False,
                },
                status=409,
            )

        if gateway_payment.get("currency") != "INR":
            return JsonResponse(
                {
                    "error": (
                        "Gateway payment currency could not be verified. "
                        "The order has not been cancelled."
                    ),
                },
                status=409,
            )

        try:
            gateway_amount = int(gateway_payment.get("amount"))
        except (TypeError, ValueError):
            return JsonResponse(
                {
                    "error": (
                        "Gateway payment amount could not be verified. "
                        "The order has not been cancelled."
                    ),
                },
                status=409,
            )

        if gateway_amount != expected_amount:
            return JsonResponse(
                {
                    "error": (
                        "Gateway payment amount does not match. "
                        "The order has not been cancelled."
                    ),
                },
                status=409,
            )

    # Lock the records and recheck the deadline and statuses.
    # The webhook or another request may have changed them while
    # Razorpay was being queried.
    with transaction.atomic():
        locked_order = (
            Order.objects.select_for_update()
            .filter(
                pk=order.pk,
                user=request.user,
                status="pending",
                delivery_method="Razorpay",
            )
            .first()
        )

        if locked_order is None:
            return JsonResponse(
                {
                    "message": "The order is no longer awaiting payment.",
                    "retry_allowed": False,
                },
                status=409,
            )

        locked_payment = (
            Payment.objects.select_for_update()
            .filter(
                pk=payment.pk,
                order=locked_order,
            )
            .first()
        )

        if locked_payment is None:
            return JsonResponse(
                {"error": "Payment record not found."},
                status=404,
            )

        if locked_payment.status in ("paid", "success"):
            return JsonResponse(
                {
                    "message": "Payment has already been completed.",
                    "retry_allowed": False,
                },
                status=409,
            )

        if (
            locked_payment.razorpay_order_id
            != payment.razorpay_order_id
            or locked_payment.status not in ("created", "failed")
            or locked_payment.retry_deadline is None
            or timezone.now() < locked_payment.retry_deadline
        ):
            return JsonResponse(
                {
                    "error": (
                        "The payment is no longer eligible for expiry."
                    ),
                    "retry_allowed": False,
                },
                status=409,
            )

        # The gateway confirmed that all returned payment attempts failed.
        if locked_payment.status == "created":
            locked_payment.status = "failed"
            locked_payment.save(
                update_fields=["status", "updated_at"]
            )

        locked_order.status = "cancelled"
        locked_order.save(
            update_fields=["status", "updated_at"]
        )

        OrderStatusHistory.objects.create(
            order=locked_order,
            status="cancelled",
        )

    return JsonResponse(
        {
            "message": "Payment retry period expired. Order cancelled.",
            "order_number": order.order_number,
            "payment_status": "failed",
            "order_status": "cancelled",
            "retry_allowed": False,
        },
        status=200,
    )
