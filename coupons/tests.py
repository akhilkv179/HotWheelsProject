
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from coupons.models import Coupon, CouponUsage
from coupons.services import (
    calculate_coupon_discount,
    record_coupon_usage,
)
from orders.models import Order


class CouponServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="coupon_test_user",
            email="coupon-test@example.com",
            password="Test-password-123",
        )

        now = timezone.now()

        self.coupon = Coupon.objects.create(
            code="SAVE10",
            coupon_name="Save 10 Percent",
            discount_type="percentage",
            discount_value=Decimal("10.00"),
            minimum_spend=Decimal("100.00"),
            maximum_discount=500,
            usage_limit=10,
            used_count=0,
            start_date=now - timedelta(days=1),
            expiry_date=now + timedelta(days=7),
            status="active",
        )

    def test_percentage_coupon_calculates_discount(self):
        coupon, discount = calculate_coupon_discount(
            "SAVE10",
            Decimal("200.00"),
        )

        self.assertEqual(coupon.pk, self.coupon.pk)
        self.assertEqual(discount, Decimal("20.00"))

    def test_percentage_coupon_respects_maximum_discount(self):
        self.coupon.discount_value = Decimal("50.00")
        self.coupon.maximum_discount = 30
        self.coupon.save(
            update_fields=["discount_value", "maximum_discount"]
        )

        coupon, discount = calculate_coupon_discount(
            "SAVE10",
            Decimal("200.00"),
        )

        self.assertEqual(coupon.pk, self.coupon.pk)
        self.assertEqual(discount, Decimal("30.00"))

    def test_fixed_coupon_calculates_discount(self):
        self.coupon.discount_type = "fixed"
        self.coupon.discount_value = Decimal("25.00")
        self.coupon.save(
            update_fields=["discount_type", "discount_value"]
        )

        coupon, discount = calculate_coupon_discount(
            "SAVE10",
            Decimal("200.00"),
        )

        self.assertEqual(coupon.pk, self.coupon.pk)
        self.assertEqual(discount, Decimal("25.00"))

    def test_invalid_coupon_code_is_rejected(self):
        with self.assertRaisesMessage(
            ValidationError,
            "Invalid coupon code.",
        ):
            calculate_coupon_discount(
                "DOESNOTEXIST",
                Decimal("200.00"),
            )

    def test_expired_coupon_is_rejected(self):
        self.coupon.expiry_date = timezone.now() - timedelta(days=1)
        self.coupon.save(update_fields=["expiry_date"])

        with self.assertRaisesMessage(
            ValidationError,
            "This coupon has expired.",
        ):
            calculate_coupon_discount(
                "SAVE10",
                Decimal("200.00"),
            )

    def test_inactive_coupon_is_rejected(self):
        self.coupon.status = "inactive"
        self.coupon.save(update_fields=["status"])

        with self.assertRaisesMessage(
            ValidationError,
            "This coupon is not active.",
        ):
            calculate_coupon_discount(
                "SAVE10",
                Decimal("200.00"),
            )

    def test_minimum_spend_is_enforced(self):
        with self.assertRaisesMessage(
            ValidationError,
            "Minimum spend of ₹100.00 is required.",
        ):
            calculate_coupon_discount(
                "SAVE10",
                Decimal("50.00"),
            )

    def test_usage_limit_is_enforced(self):
        self.coupon.used_count = self.coupon.usage_limit
        self.coupon.save(update_fields=["used_count"])

        with self.assertRaisesMessage(
            ValidationError,
            "This coupon's usage limit has been reached.",
        ):
            calculate_coupon_discount(
                "SAVE10",
                Decimal("200.00"),
            )

    def test_coupon_usage_is_recorded_and_count_increases(self):
        order = Order.objects.create(
            user=self.user,
            address=None,
            coupon=None,
            order_number="HW-COUPON-TEST-001",
            status="pending",
            subtotal=Decimal("200.00"),
            discount_amount=Decimal("20.00"),
            shipping_amount=Decimal("0.00"),
            total_amount=Decimal("180.00"),
            delivery_method="Razorpay",
        )

        record_coupon_usage(
            coupon=self.coupon,
            order=order,
            user=self.user,
            discount_amount=Decimal("20.00"),
        )

        self.coupon.refresh_from_db()
        order.refresh_from_db()

        self.assertEqual(self.coupon.used_count, 1)
        self.assertEqual(order.coupon_id, self.coupon.pk)

        usage = CouponUsage.objects.get(
            coupon=self.coupon,
            order=order,
            user=self.user,
        )

        self.assertEqual(
            usage.discount_amount,
            Decimal("20.00"),
        )
