
import hashlib
import hmac
import json
import logging
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from orders.models import Order, OrderStatusHistory
from payments.models import Payment
from wallet.services.refund_service import credit_wallet_refund


logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def razorpay_webhook_view(request):
    webhook_secret = getattr(
        settings,
        "RAZORPAY_WEBHOOK_SECRET",
        "",
    )

    if not webhook_secret:
        logger.error("Razorpay webhook secret is not configured.")
        return JsonResponse(
            {"error": "Webhook is not configured."},
            status=503,
        )

    raw_body = request.body
    received_signature = request.headers.get(
        "X-Razorpay-Signature",
        "",
    )

    if not received_signature:
        return JsonResponse(
            {"error": "Missing webhook signature."},
            status=400,
        )

    expected_signature = hmac.new(
        webhook_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(
        expected_signature,
        received_signature,
    ):
        logger.warning("Rejected webhook with an invalid signature.")
        return JsonResponse(
            {"error": "Invalid webhook signature."},
            status=400,
        )

    try:
        data = json.loads(raw_body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"error": "Invalid webhook payload."},
            status=400,
        )

    if not isinstance(data, dict):
        return JsonResponse(
            {"error": "Invalid webhook payload."},
            status=400,
        )

    if data.get("event") != "payment.captured":
        return JsonResponse(
            {"message": "Event ignored."},
            status=200,
        )

    payload = data.get("payload")
    if not isinstance(payload, dict):
        return JsonResponse(
            {"error": "Payment payload is missing."},
            status=400,
        )

    payment_payload = payload.get("payment")
    if not isinstance(payment_payload, dict):
        return JsonResponse(
            {"error": "Payment details are missing."},
            status=400,
        )

    entity = payment_payload.get("entity")
    if not isinstance(entity, dict):
        return JsonResponse(
            {"error": "Payment details are invalid."},
            status=400,
        )

    gateway_order_id = entity.get("order_id")
    gateway_payment_id = entity.get("id")

    if not isinstance(gateway_order_id, str) or not gateway_order_id:
        return JsonResponse(
            {"error": "Razorpay order ID is missing."},
            status=400,
        )

    if not isinstance(gateway_payment_id, str) or not gateway_payment_id:
        return JsonResponse(
            {"error": "Razorpay payment ID is missing."},
            status=400,
        )

    if entity.get("status") != "captured":
        return JsonResponse(
            {"message": "Payment is not captured."},
            status=200,
        )

    if entity.get("currency") != "INR":
        return JsonResponse(
            {"error": "Unexpected payment currency."},
            status=400,
        )

    try:
        gateway_amount = int(entity.get("amount"))
    except (TypeError, ValueError):
        return JsonResponse(
            {"error": "Invalid payment amount."},
            status=400,
        )

    candidate = Payment.objects.filter(
        payment_method="razorpay",
        razorpay_order_id=gateway_order_id,
    ).values("pk", "order_id").first()

    if candidate is None:
        logger.warning(
            "No payment record found for Razorpay order %s.",
            gateway_order_id,
        )
        return JsonResponse(
            {"error": "Payment record not found."},
            status=404,
        )

    try:
        with transaction.atomic():
            order = Order.objects.select_for_update().get(
                pk=candidate["order_id"],
            )

            payment = Payment.objects.select_for_update().get(
                pk=candidate["pk"],
                order=order,
            )

            if order.delivery_method.strip().lower() != "razorpay":
                return JsonResponse(
                    {"error": "Order payment method mismatch."},
                    status=400,
                )

            expected_amount = int(
                (payment.amount * Decimal("100")).quantize(
                    Decimal("1"),
                    rounding=ROUND_HALF_UP,
                )
            )

            if gateway_amount != expected_amount:
                logger.error(
                    "Captured amount mismatch for payment %s.",
                    gateway_payment_id,
                )
                return JsonResponse(
                    {"error": "Payment amount mismatch."},
                    status=400,
                )

            # A previously processed capture must not be credited twice.
            if payment.status in ("paid", "success"):
                if payment.transaction_id == gateway_payment_id:
                    return JsonResponse(
                        {
                            "message": "Payment already processed.",
                            "order_number": order.order_number,
                        },
                        status=200,
                    )

                logger.warning(
                    "Different captured payment ID for already-paid "
                    "payment record %s.",
                    payment.pk,
                )
                return JsonResponse(
                    {"message": "Payment record already processed."},
                    status=200,
                )

            # Failed is allowed here because the gateway's captured
            # event is authoritative evidence that payment succeeded.
            if payment.status not in ("created", "failed"):
                return JsonResponse(
                    {"message": "Payment is not eligible for processing."},
                    status=200,
                )

            deadline_expired = (
                payment.retry_deadline is not None
                and timezone.now() >= payment.retry_deadline
            )

            refund_to_wallet = (
                order.status != "pending"
                or payment.amount != order.total_amount
                or deadline_expired
            )

            if refund_to_wallet:
                # Use a stable transaction ID so the refund service can
                # reject duplicate credits for this payment.
                credit_wallet_refund(
                    user=order.user,
                    amount=payment.amount,
                    transaction_id=(
                        f"RAZORPAY-CAPTURE-REFUND-{payment.pk}"
                    ),
                    reference_id=order.order_number,
                )

            payment.transaction_id = gateway_payment_id
            payment.status = "paid"
            payment.paid_at = timezone.now()
            payment.save(
                update_fields=[
                    "transaction_id",
                    "status",
                    "paid_at",
                    "updated_at",
                ]
            )

            if not refund_to_wallet:
                order.status = "confirmed"
                order.save(
                    update_fields=["status", "updated_at"]
                )

                OrderStatusHistory.objects.create(
                    order=order,
                    status="confirmed",
                )

                message = "Payment captured and order confirmed."

            else:
                # If the order was still pending but the retry deadline
                # had passed, close it rather than leaving it pending.
                if order.status == "pending":
                    order.status = "cancelled"
                    order.save(
                        update_fields=["status", "updated_at"]
                    )

                    OrderStatusHistory.objects.create(
                        order=order,
                        status="cancelled",
                    )

                message = (
                    "Payment captured, but the order could not be "
                    "confirmed. The captured amount was credited "
                    "to the customer's wallet."
                )

    except (Order.DoesNotExist, Payment.DoesNotExist):
        return JsonResponse(
            {"error": "Order or payment record not found."},
            status=404,
        )

    except ValidationError:
        logger.exception(
            "Wallet refund failed for captured payment %s.",
            gateway_payment_id,
        )
        return JsonResponse(
            {"error": "Payment refund could not be processed."},
            status=500,
        )

    except Exception:
        logger.exception(
            "Failed to process Razorpay capture %s.",
            gateway_payment_id,
        )
        return JsonResponse(
            {"error": "Unable to process captured payment."},
            status=500,
        )

    return JsonResponse(
        {
            "message": message,
            "order_number": order.order_number,
            "payment_status": "paid",
            "order_status": order.status,
        },
        status=200,
    )
