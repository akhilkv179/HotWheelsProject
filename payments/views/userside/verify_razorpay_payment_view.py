import hashlib
import hmac
import json
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
def verify_razorpay_payment_view(request):
    key_id = getattr(settings,"RAZORPAY_KEY_ID", "")
    key_secret = getattr(settings,"RAZORPAY_KEY_SECRET", "")

    if not key_id or not key_secret:
        return JsonResponse(
            {"error": "Razorpay is not configured correctly."},
            status=503,
        )

    # Read and validate the JSON request body.
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

    razorpay_order_id = data.get("razorpay_order_id")
    razorpay_payment_id = data.get("razorpay_payment_id")
    razorpay_signature = data.get("razorpay_signature")
    order_number = data.get("order_number")

    if not all(
        [
            razorpay_order_id,
            razorpay_payment_id,
            razorpay_signature,
            order_number,
        ]
    ):
        return JsonResponse(
            {"error": "Missing payment verification details."},
            status=400,
        )

    # Find the order belonging to the current customer.
    order = Order.objects.filter(
        order_number=order_number,
        user=request.user,
    ).first()

    if not order:
        return JsonResponse(
            {"error": "Order not found."},
            status=404,
        )

    if order.delivery_method != "Razorpay":
        return JsonResponse(
            {"error": "This order is not configured for Razorpay."},
            status=400,
        )

    # Find the payment using the stored gateway order ID.
    payment = Payment.objects.filter(
        order=order,
        payment_method="razorpay",
        razorpay_order_id=razorpay_order_id,
    ).first()

    if not payment:
        return JsonResponse(
            {"error": "Payment record not found."},
            status=404,
        )

    # Treat already verified requests as idempotent.
    if payment.status in ("paid", "success"):
        if payment.transaction_id == razorpay_payment_id:
            # Normalize records written by the previous view version.
            if payment.status == "success":
                payment.status = "paid"
                payment.save(
                    update_fields=["status", "updated_at"]
                )

            return JsonResponse(
                {
                    "message": "Payment has already been verified.",
                    "order_number": order.order_number,
                },
                status=200,
            )

        return JsonResponse(
            {"error": "This order has already been paid."},
            status=409,
        )

    if payment.status != "created":
        return JsonResponse(
            {"error": "This payment cannot be verified."},
            status=400,
        )

    if order.status != "pending":
        return JsonResponse(
            {"error": "This order is no longer awaiting payment."},
            status=409,
        )

    # Use the gateway order ID stored in the database.
    generated_signature = hmac.new(
        key_secret.encode("utf-8"),
        (
            f"{payment.razorpay_order_id}|"
            f"{razorpay_payment_id}"
        ).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(
        generated_signature,
        razorpay_signature,
    ):
        return JsonResponse(
            {"error": "Payment signature verification failed."},
            status=400,
        )

    # Fetch the payment from Razorpay and verify its actual status.
    try:
        client = razorpay.Client(
            auth=(key_id, key_secret)
        )

        gateway_payment = client.payment.fetch(
            razorpay_payment_id
        )

    except Exception:
        logger.exception(
            "Unable to fetch Razorpay payment %s",
            razorpay_payment_id,
        )

        return JsonResponse(
            {
                "error": (
                    "Unable to confirm payment status with Razorpay. "
                    "Please try again."
                )
            },
            status=502,
        )

    # Ensure the gateway payment belongs to this order.
    if gateway_payment.get("order_id") != payment.razorpay_order_id:
        return JsonResponse(
            {"error": "The payment does not match this order."},
            status=400,
        )

    # Compare the gateway amount with the stored payment amount.
    expected_amount = int(
        (payment.amount * Decimal("100")).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )

    try:
        gateway_amount = int(gateway_payment.get("amount"))
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

    # Do not confirm an order until Razorpay reports it as captured.
    if gateway_payment.get("status") != "captured":
        return JsonResponse(
            {
                "error": (
                    "Payment is not captured yet. "
                    "The order has not been confirmed."
                )
            },
            status=409,
        )

    # Re-lock and recheck state in case another request completed payment.
    with transaction.atomic():
        locked_order = (
            Order.objects.select_for_update()
            .filter(
                pk=order.pk,
                user=request.user,
            )
            .first()
        )

        locked_payment = (
            Payment.objects.select_for_update()
            .filter(
                pk=payment.pk,
                order=locked_order,
            )
            .first()
            if locked_order
            else None
        )

        if not locked_order or not locked_payment:
            return JsonResponse(
                {"error": "Order or payment record not found."},
                status=404,
            )

        if locked_payment.status in ("paid", "success"):
            if (
                locked_payment.transaction_id
                == razorpay_payment_id
            ):
                if locked_payment.status == "success":
                    locked_payment.status = "paid"
                    locked_payment.save(
                        update_fields=["status", "updated_at"]
                    )

                return JsonResponse(
                    {
                        "message": (
                            "Payment has already been verified."
                        ),
                        "order_number": locked_order.order_number,
                    },
                    status=200,
                )

            return JsonResponse(
                {"error": "This order has already been paid."},
                status=409,
            )

        if (
            locked_payment.status != "created"
            or locked_order.status != "pending"
        ):
            return JsonResponse(
                {"error": "This order is no longer awaiting payment."},
                status=409,
            )

        # Record the verified and captured payment.
        locked_payment.transaction_id = razorpay_payment_id
        locked_payment.status = "paid"
        locked_payment.paid_at = timezone.now()
        locked_payment.save(
            update_fields=[
                "transaction_id",
                "status",
                "paid_at",
                "updated_at",
            ]
        )

        # Confirm the order only after server-side verification.
        locked_order.status = "confirmed"
        locked_order.save(
            update_fields=["status", "updated_at"]
        )

        # Keep the order's status history consistent.
        OrderStatusHistory.objects.create(
            order=locked_order,
            status="confirmed",
        )

    return JsonResponse(
        {
            "message": "Payment verified successfully.",
            "order_number": order.order_number,
        },
        status=200,
    )