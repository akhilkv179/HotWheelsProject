
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from coupons.models import Coupon, CouponUsage


ZERO = Decimal("0.00")
CENT = Decimal("0.01")


@transaction.atomic
def calculate_coupon_discount(code, eligible_subtotal):
    """
    Validate a coupon and calculate its discount.

    eligible_subtotal should be the cart amount after product
    offer discounts and before applying the coupon.
    """

    code = (code or "").strip()

    try:
        eligible_subtotal = Decimal(str(eligible_subtotal))
    except (ValueError, TypeError, ArithmeticError):
        raise ValidationError("Invalid cart amount.")

    if (
        not eligible_subtotal.is_finite()
        or eligible_subtotal < ZERO
    ):
        raise ValidationError("Invalid cart amount.")

    if not code:
        return None, ZERO

    # Lock the coupon while checking its availability and usage limit.
    coupon = (
        Coupon.objects.select_for_update()
        .filter(code__iexact=code)
        .first()
    )

    if coupon is None:
        raise ValidationError("Invalid coupon code.")

    current_time = timezone.now()

    if coupon.status.strip().lower() != "active":
        raise ValidationError("This coupon is not active.")

    if current_time < coupon.start_date:
        raise ValidationError("This coupon is not available yet.")

    if current_time > coupon.expiry_date:
        raise ValidationError("This coupon has expired.")

    if coupon.used_count >= coupon.usage_limit:
        raise ValidationError("This coupon's usage limit has been reached.")

    if eligible_subtotal < coupon.minimum_spend:
        raise ValidationError(
            f"Minimum spend of ₹{coupon.minimum_spend} is required."
        )

    discount_type = coupon.discount_type.strip().lower()
    discount_value = coupon.discount_value

    # Calculate a percentage discount.
    if discount_type in ("percentage", "percent"):
        if not ZERO < discount_value <= Decimal("100"):
            raise ValidationError(
                "The coupon percentage must be greater than 0 "
                "and no more than 100."
            )

        discount_amount = (
            eligible_subtotal * discount_value / Decimal("100")
        ).quantize(CENT, rounding=ROUND_HALF_UP)

        # Apply the maximum discount when a positive cap is configured.
        if coupon.maximum_discount > 0:
            discount_amount = min(
                discount_amount,
                Decimal(coupon.maximum_discount),
            )

    # Calculate a fixed-amount discount.
    elif discount_type in ("fixed", "flat", "fixed_amount"):
        if discount_value <= ZERO:
            raise ValidationError(
                "The fixed coupon discount must be greater than zero."
            )

        discount_amount = discount_value.quantize(
            CENT,
            rounding=ROUND_HALF_UP,
        )

    else:
        raise ValidationError(
            "Unsupported coupon discount type."
        )

    # A coupon cannot discount more than the eligible cart amount.
    discount_amount = min(discount_amount, eligible_subtotal)

    if discount_amount <= ZERO:
        raise ValidationError(
            "This coupon does not provide a valid discount."
        )

    return coupon, discount_amount


@transaction.atomic
def record_coupon_usage(coupon, order, user, discount_amount):
    """Record a successful coupon use and increment its usage count."""

    if coupon is None or discount_amount <= ZERO:
        return None

    # Re-lock and recheck the usage limit before recording.
    locked_coupon = Coupon.objects.select_for_update().get(
        pk=coupon.pk
    )

    if locked_coupon.used_count >= locked_coupon.usage_limit:
        raise ValidationError(
            "This coupon's usage limit has been reached."
        )

    coupon_usage = CouponUsage.objects.create(
        coupon=locked_coupon,
        order=order,
        user=user,
        discount_amount=discount_amount,
        used_at=timezone.now(),
    )

    locked_coupon.used_count += 1
    locked_coupon.save(
        update_fields=["used_count", "updated_at"]
    )

    # Associate the applied coupon with the order.
    order.coupon = locked_coupon
    order.save(update_fields=["coupon", "updated_at"])

    return coupon_usage
