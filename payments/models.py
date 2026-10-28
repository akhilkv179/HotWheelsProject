from django.db import models
from orders.models import Order


class Payment(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="payments"
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    payment_method = models.CharField(max_length=100)
    status = models.CharField(max_length=100)

    # Razorpay order ID
    razorpay_order_id = models.CharField(
        max_length=255,
        blank=True,
        default=""
    )

    # Razorpay payment transaction ID
    transaction_id = models.CharField(
        max_length=255,
        blank=True,
        default=""
    )

    # Deadline for retrying a cancelled or failed payment
    retry_deadline = models.DateTimeField(
        null=True,
        blank=True,
    )

    paid_at = models.DateTimeField(
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.order.order_number} - {self.transaction_id or self.status}"


class Refund(models.Model):
    return_request = models.OneToOneField(
        "orders.Return",
        on_delete=models.CASCADE,
        related_name="refund"
    )
    wallet_transaction = models.OneToOneField(
        "wallet.WalletTransaction",
        on_delete=models.CASCADE,
        related_name="refund"
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    status = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(
        null=True,
        blank=True
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Refund - {self.amount}"