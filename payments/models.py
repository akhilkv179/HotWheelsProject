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
    transaction_id = models.CharField(max_length=255)
    paid_at = models.DateTimeField(
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.order.order_number} - {self.transaction_id}"



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
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Refund - {self.amount}"