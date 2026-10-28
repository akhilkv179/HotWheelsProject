
import hashlib
import hmac
import json
import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import razorpay

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from wallet.models import Wallet, WalletTopUp
from wallet.services.transaction_service import (
    process_wallet_transaction,
)

logger = logging.getLogger(__name__)


@login_required
@require_POST
def create_wallet_topup_order(request):
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

    try:
        amount = Decimal(str(data.get("amount", "")))
    except (InvalidOperation, ValueError, TypeError):
        return JsonResponse(
            {"error": "Enter a valid amount."},
            status=400,
        )

    if not amount.is_finite() or amount <= Decimal("0.00"):
        return JsonResponse(
            {"error": "Amount must be greater than zero."},
            status=400,
        )

    if amount.as_tuple().exponent < -2:
        return JsonResponse(
            {"error": "Amount cannot have more than two decimal places."},
            status=400,
        )

    if amount > Decimal("99999999.99"):
        return JsonResponse(
            {"error": "Amount is too large."},
            status=400,
        )

    amount = amount.quantize(Decimal("0.01"))

    wallet = Wallet.objects.filter(
        user=request.user,
        is_active=True,
    ).first()

    if not wallet:
        return JsonResponse(
            {"error": "An active wallet was not found."},
            status=404,
        )

    amount_in_paise = int(
        (amount * Decimal("100")).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )

    try:
        client = razorpay.Client(auth=(key_id, key_secret))

        gateway_order = client.order.create(
            data={
                "amount": amount_in_paise,
                "currency": "INR",
                "receipt": (
                    f"wallet-{wallet.pk}-"
                    f"{timezone.now().timestamp()}"
                ),
                "notes": {
                    "purpose": "wallet_topup",
                    "user_id": str(request.user.pk),
                    "wallet_id": str(wallet.pk),
                },
            }
        )

        topup = WalletTopUp.objects.create(
            wallet=wallet,
            amount=amount,
            razorpay_order_id=gateway_order["id"],
            status="created",
        )

    except Exception:
        logger.exception(
            "Failed to create wallet top-up order for user %s",
            request.user.pk,
        )
        return JsonResponse(
            {"error": "Unable to start payment. Please try again."},
            status=502,
        )

    return JsonResponse(
        {
            "key_id": key_id,
            "razorpay_order_id": topup.razorpay_order_id,
            "amount": amount_in_paise,
            "currency": "INR",
            "topup_id": topup.pk,
        },
        status=201,
    )


@login_required
@require_POST
def verify_wallet_topup_payment(request):
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

    razorpay_order_id = data.get("razorpay_order_id")
    razorpay_payment_id = data.get("razorpay_payment_id")
    razorpay_signature = data.get("razorpay_signature")

    if not all(
        [
            razorpay_order_id,
            razorpay_payment_id,
            razorpay_signature,
        ]
    ):
        return JsonResponse(
            {"error": "Missing payment verification details."},
            status=400,
        )

    topup = WalletTopUp.objects.filter(
        razorpay_order_id=razorpay_order_id,
        wallet__user=request.user,
    ).first()

    if not topup:
        return JsonResponse(
            {"error": "Wallet top-up record not found."},
            status=404,
        )

    # Verify the Razorpay signature.
    generated_signature = hmac.new(
        key_secret.encode("utf-8"),
        (
            f"{topup.razorpay_order_id}|"
            f"{razorpay_payment_id}"
        ).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(
        generated_signature,
        str(razorpay_signature),
    ):
        return JsonResponse(
            {"error": "Payment signature verification failed."},
            status=400,
        )

    # Fetch the payment directly from Razorpay.
    try:
        client = razorpay.Client(auth=(key_id, key_secret))
        gateway_payment = client.payment.fetch(razorpay_payment_id)

    except Exception:
        logger.exception(
            "Unable to fetch Razorpay payment %s",
            razorpay_payment_id,
        )
        return JsonResponse(
            {"error": "Unable to confirm payment with Razorpay."},
            status=502,
        )

    if gateway_payment.get("order_id") != topup.razorpay_order_id:
        return JsonResponse(
            {"error": "Payment does not match this wallet top-up."},
            status=400,
        )

    expected_amount = int(
        (topup.amount * Decimal("100")).quantize(
            Decimal("1"),
            rounding=ROUND_HALF_UP,
        )
    )

    try:
        gateway_amount = int(gateway_payment.get("amount"))
    except (TypeError, ValueError):
        return JsonResponse(
            {"error": "Invalid payment amount from Razorpay."},
            status=400,
        )

    if gateway_amount != expected_amount:
        return JsonResponse(
            {"error": "Payment amount does not match the top-up amount."},
            status=400,
        )

    if gateway_payment.get("currency") != "INR":
        return JsonResponse(
            {"error": "Payment currency must be INR."},
            status=400,
        )

    if gateway_payment.get("status") != "captured":
        return JsonResponse(
            {
                "error": (
                    "Payment has not been captured. "
                    "The wallet has not been credited."
                )
            },
            status=409,
        )

    try:
        with transaction.atomic():
            locked_topup = (
                WalletTopUp.objects.select_for_update()
                .filter(
                    pk=topup.pk,
                    wallet__user=request.user,
                )
                .first()
            )

            if not locked_topup:
                return JsonResponse(
                    {"error": "Wallet top-up record not found."},
                    status=404,
                )

            # Make repeated verification requests safe.
            if locked_topup.status == "paid":
                if (
                    locked_topup.razorpay_payment_id
                    == razorpay_payment_id
                ):
                    return JsonResponse(
                        {
                            "message": "Wallet top-up already processed.",
                            "amount": str(locked_topup.amount),
                            "razorpay_payment_id": razorpay_payment_id,
                        },
                        status=200,
                    )

                return JsonResponse(
                    {
                        "error": (
                            "This top-up has already been processed."
                        )
                    },
                    status=409,
                )

            if locked_topup.status != "created":
                return JsonResponse(
                    {"error": "This top-up cannot be processed."},
                    status=409,
                )

            # Credit the wallet and record the transaction atomically.
            process_wallet_transaction(
                wallet_id=locked_topup.wallet_id,
                amount=locked_topup.amount,
                transaction_type="credit",
                transaction_id=(
                    f"RAZORPAY-TOPUP-{razorpay_payment_id}"
                ),
                reference_id=locked_topup.razorpay_order_id,
            )

            locked_topup.razorpay_payment_id = razorpay_payment_id
            locked_topup.status = "paid"
            locked_topup.paid_at = timezone.now()

            locked_topup.save(
                update_fields=[
                    "razorpay_payment_id",
                    "status",
                    "paid_at",
                ]
            )

    except ValidationError as exc:
        return JsonResponse(
            {"error": str(exc)},
            status=409,
        )

    except IntegrityError:
        # The database constraint prevents a payment ID from being
        # attached to more than one top-up. The atomic block rolls
        # back the wallet credit if this save fails.
        logger.warning(
            "Duplicate Razorpay payment ID rejected: %s",
            razorpay_payment_id,
        )
        return JsonResponse(
            {
                "error": (
                    "This Razorpay payment has already been used. "
                    "The wallet was not credited again."
                )
            },
            status=409,
        )

    except Exception:
        logger.exception(
            "Failed to credit wallet top-up %s",
            razorpay_order_id,
        )
        return JsonResponse(
            {
                "error": (
                    "Unable to update the wallet. Please contact support."
                )
            },
            status=500,
        )

    return JsonResponse(
        {
            "message": "Wallet funded successfully.",
            "amount": str(topup.amount),
            "razorpay_payment_id": razorpay_payment_id,
        },
        status=200,
    )
