import logging
from decimal import Decimal, ROUND_HALF_UP

import razorpay

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from orders.models import Order
from payments.models import Payment

logger = logging.getLogger(__name__)


@login_required
@require_POST
def create_razorpay_order(request, order_number):
    key_id = getattr(settings, "RAZORPAY_KEY_ID", "")
    key_secret = getattr(settings, "RAZORPAY_KEY_SECRET", "")

    if not key_id or not key_secret:
        return JsonResponse(
            {"error": "Razorpay is not configured correctly."},
            status=503,
        )

    with transaction.atomic():
        order = get_object_or_404(
            Order.objects.select_for_update(),
            order_number=order_number,
            user=request.user,
        )

        if order.delivery_method != "Razorpay":
            return JsonResponse(
                {"error": "This order is not configured for Razorpay."},
                status=400,
            )

        if order.status != "pending":
            return JsonResponse(
                {"error": "This order is not awaiting payment."},
                status=400,
            )

        amount_in_paise = int(
            (order.total_amount * Decimal("100")).quantize(
                Decimal("1"),
                rounding=ROUND_HALF_UP,
            )
        )

        if amount_in_paise <= 0:
            return JsonResponse(
                {"error": "The order amount must be greater than zero."},
                status=400,
            )

        existing_payment = (
            Payment.objects.select_for_update()
            .filter(
                order=order,
                payment_method="razorpay",
            )
            .exclude(razorpay_order_id="")
            .order_by("-created_at")
            .first()
        )

        if existing_payment:
            if existing_payment.amount != order.total_amount:
                return JsonResponse(
                    {
                        "error": (
                            "The payment amount no longer matches "
                            "the order total."
                        )
                    },
                    status=409,
                )

            if existing_payment.status in ("paid", "success"):
                return JsonResponse(
                    {
                        "error": "This order has already been paid.",
                        "retry_allowed": False,
                    },
                    status=409,
                )

            # Do not permit another attempt after the original
            # retry deadline, even if the status is "created".
            if (
                existing_payment.retry_deadline is not None
                and timezone.now() >= existing_payment.retry_deadline
            ):
                return JsonResponse(
                    {
                        "error": "The payment retry period has expired.",
                        "retry_allowed": False,
                        "retry_deadline": (
                            existing_payment.retry_deadline.isoformat()
                        ),
                    },
                    status=409,
                )

            if existing_payment.status == "failed":
                if existing_payment.retry_deadline is None:
                    return JsonResponse(
                        {
                            "error": (
                                "The payment retry deadline is missing. "
                                "A new retry cannot be started."
                            ),
                            "retry_allowed": False,
                        },
                        status=409,
                    )

                # Preserve retry_deadline. Never extend the window here.
                existing_payment.status = "created"
                existing_payment.save(
                    update_fields=["status", "updated_at"]
                )

            elif existing_payment.status != "created":
                return JsonResponse(
                    {
                        "error": "This payment cannot be retried.",
                        "retry_allowed": False,
                    },
                    status=409,
                )

            return JsonResponse(
                {
                    "key_id": key_id,
                    "razorpay_order_id": (
                        existing_payment.razorpay_order_id
                    ),
                    "amount": amount_in_paise,
                    "currency": "INR",
                    "order_number": order.order_number,
                }
            )

        try:
            client = razorpay.Client(
                auth=(key_id, key_secret)
            )

            gateway_order = client.order.create(
                data={
                    "amount": amount_in_paise,
                    "currency": "INR",
                    "receipt": order.order_number,
                    "notes": {
                        "django_order_number": order.order_number,
                        "user_id": str(request.user.id),
                    },
                }
            )

            Payment.objects.create(
                order=order,
                amount=order.total_amount,
                payment_method="razorpay",
                status="created",
                razorpay_order_id=gateway_order["id"],
                transaction_id="",
            )

            return JsonResponse(
                {
                    "key_id": key_id,
                    "razorpay_order_id": gateway_order["id"],
                    "amount": amount_in_paise,
                    "currency": "INR",
                    "order_number": order.order_number,
                }
            )

        except Exception:
            logger.exception(
                "Failed to create Razorpay order for %s",
                order.order_number,
            )

            return JsonResponse(
                {
                    "error": "Unable to start payment. Please try again."
                },
                status=502,
            )