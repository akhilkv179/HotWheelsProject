from django.db import models

from accounts.models import User


class Coupon(models.Model):
    code = models.CharField(max_length=100)
    coupon_name = models.CharField(max_length=255)
    discount_type = models.CharField(max_length=50)
    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    minimum_spend = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    maximum_discount = models.IntegerField()
    usage_limit = models.IntegerField()
    used_count = models.IntegerField(default=0)
    start_date = models.DateTimeField()
    expiry_date = models.DateTimeField()
    status = models.CharField(max_length=50)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.code


class CouponUsage(models.Model):
    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.CASCADE,
        related_name="usages"
    )
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="coupon_usages"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="coupon_usages"
    )
    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    used_at = models.DateTimeField()

    def __str__(self):
        return f"{self.coupon.code} - {self.user.name}"