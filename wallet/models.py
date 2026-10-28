
from django.db import models
from django.db.models import Q

from accounts.models import User


class Wallet(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="wallet",
    )
    balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.00,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.name}'s Wallet"


class WalletTransaction(models.Model):
    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    balance_after = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_id = models.CharField(max_length=255)
    transaction_type = models.CharField(max_length=100)
    reference_id = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["wallet", "transaction_id"],
                name="unique_wallet_transaction_id",
            ),
        ]

    def __str__(self):
        return f"{self.wallet.user.name} - {self.transaction_type}"


class WalletTopUp(models.Model):
    wallet = models.ForeignKey(
        Wallet,
        on_delete=models.CASCADE,
        related_name="topups",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    razorpay_order_id = models.CharField(
        max_length=255,
        unique=True,
    )
    razorpay_payment_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )
    status = models.CharField(max_length=20, default="created")
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["razorpay_payment_id"],
                condition=~Q(razorpay_payment_id=""),
                name="unique_wallet_topup_razorpay_payment",
            ),
        ]

    def __str__(self):
        return (
            f"Wallet top-up - {self.wallet.user.name} - "
            f"₹{self.amount} ({self.status})"
        )
