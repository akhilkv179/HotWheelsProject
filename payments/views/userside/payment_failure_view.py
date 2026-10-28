
import json
import logging
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

import razorpay

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from orders.models import Order
from payments.models import Payment


logger = logging.getLogger(__name__)


@login_required
@require_POST
def record_razorpay_payment_failure(request):
    key_id = getattr(settings, "RAZORPAY_KEY_ID", "")
    key_secret = getattr(settings, "RAZORPAY_KEY_SECRET", "")

    if not key_id or not key_secret:
        return JsonResponse(
            {"error": "Razorpay is not configured correctly."},
            status=503,
        )

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"error": "Invalid request data."},
            status=400,
        )

    if not isinstance(data, dict):
        return JsonResponse(
            {"error": "Invalid request data."},
            status=400,
        )

    order_number = data.get("order_number")
    razorpay_order_id = data.get("razorpay_order_id")
    razorpay_payment_id = data.get("razorpay_payment_id")

    if not all(
        isinstance(value, str) and value.strip()
        for value in (
            order_number,
            razorpay_order_id,
            razorpay_payment_id,
        )
    ):
        return JsonResponse(
            {
                "error": (
                    "Order number, Razorpay order ID, and "
                    "Razorpay payment ID are required."
                )
            },
            status=400,
        )

    order = Order.objects.filter(
        order_number=order_number.strip(),
        user=request.user,
        delivery_method="Razorpay",
    ).first()

    if order is None:
        return JsonResponse(
            {"error": "Order not found."},
            status=404,
        )

    payment = Payment.objects.filter(
        order=order,
        payment_method="razorpay",
        razorpay_order_id=razorpay_order_id.strip(),
    ).first()

    if payment is None:
        return JsonResponse(
            {"error": "Payment record not found."},
            status=404,
        )

    if payment.status in ("paid", "success"):
        return JsonResponse(
            {
                "message": "Payment has already been confirmed.",
                "order_number": order.order_number,
                "payment_status": "paid",
                "retry_allowed": False,
            },
            status=409,
        )

    if payment.status not in ("created", "failed"):
        return JsonResponse(
            {"error": "This payment cannot be marked as failed."},
            status=409,
        )

    if order.status != "pending":
        return JsonResponse(
            {
                "error": "This order is no longer awaiting payment.",
                "order_status": order.status,
                "retry_allowed": False,
            },
            status=409,
        )

    # Verify the actual payment status with Razorpay.
    try:
        client = razorpay.Client(
            auth=(key_id, key_secret)
        )
        gateway_payment = client.payment.fetch(
            razorpay_payment_id.strip()
        )
    except Exception:
        logger.exception(
            "Unable to retrieve Razorpay payment %s",
            razorpay_payment_id,
        )
        return JsonResponse(
            {
                "error": (
                    "Unable to verify the payment status with Razorpay. "
                    "Please try again."
                )
            },
            status=502,
        )

    if gateway_payment.get("order_id") != payment.razorpay_order_id:
        return JsonResponse(
            {"error": "The payment does not match this order."},
            status=400,
        )

    try:
        gateway_amount = int(gateway_payment.get("amount"))
        expected_amount = int(
            (payment.amount * Decimal("100")).quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP,
            )
        )
    except (TypeError, ValueError):
        return JsonResponse(
            {"error": "Invalid payment amount received from Razorpay."},
            status=400,
        )

    if gateway_amount != expected_amount:
        return JsonResponse(
            {"error": "The payment amount does not match the order."},
            status=400,
        )

    if gateway_payment.get("currency") != "INR":
        return JsonResponse(
            {"error": "The payment currency does not match the order."},
            status=400,
        )

    if gateway_payment.get("status") != "failed":
        return JsonResponse(
            {
                "error": (
                    "Razorpay has not confirmed this payment as failed."
                ),
                "gateway_payment_status": gateway_payment.get("status"),
                "retry_allowed": False,
            },
            status=409,
        )

    with transaction.atomic():
        locked_order = (
            Order.objects.select_for_update()
            .filter(
                pk=order.pk,
                user=request.user,
            )
            .first()
        )

        if locked_order is None:
            return JsonResponse(
                {"error": "Order not found."},
                status=404,
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
                    "message": "Payment has already been confirmed.",
                    "retry_allowed": False,
                },
                status=409,
            )

        if locked_order.status != "pending":
            return JsonResponse(
                {
                    "error": "This order is no longer awaiting payment.",
                    "retry_allowed": False,
                },
                status=409,
            )

        if locked_payment.status != "created":
            return JsonResponse(
                {
                    "error": "This payment is no longer awaiting failure recording.",
                    "retry_allowed": False,
                },
                status=409,
            )

        # Mark this attempt as failed.
        locked_payment.status = "failed"
        update_fields = ["status", "updated_at"]

        # Start the five-minute window only once.
        # Preserve the original deadline on subsequent retries.
        if locked_payment.retry_deadline is None:
            locked_payment.retry_deadline = (
                timezone.now() + timedelta(minutes=5)
            )
            update_fields.append("retry_deadline")

        locked_payment.save(update_fields=update_fields)

        deadline = locked_payment.retry_deadline
        retry_allowed = (
            deadline is not None
            and timezone.now() < deadline
        )

        if not retry_allowed:
            return JsonResponse(
                {
                    "error": "The payment retry period has expired.",
                    "order_number": locked_order.order_number,
                    "retry_allowed": False,
                    "retry_deadline": (
                        deadline.isoformat() if deadline else None
                    ),
                },
                status=409,
            )

    return JsonResponse(
        {
            "message": "Payment failed. You can retry payment.",
            "order_number": locked_order.order_number,
            "payment_status": "failed",
            "order_status": locked_order.status,
            "retry_allowed": True,
            "retry_deadline": deadline.isoformat(),
        },
        status=200,
    )
