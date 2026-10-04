from django.db import models

from accounts.models import User


class Wallet(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="wallet"
    )
    balance = models.DecimalField(
        max_digits=10,
        decimal_places=2
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
        related_name="transactions"
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    balance_after = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    transaction_id = models.CharField(max_length=255)
    transaction_type = models.CharField(max_length=100)
    reference_id = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.wallet.user.name} - {self.transaction_type}"