
import uuid

from django.db import models
from django.utils.crypto import get_random_string

from accounts.models import User



class ReferralOffer(models.Model):
    reward_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Referral Offer - {self.reward_amount}"


class ReferralCode(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="referral_profile",
    )
    code = models.CharField(
        max_length=12,
        unique=True,
        blank=True,
    )
    token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.code:
            while True:
                candidate = get_random_string(8).upper()

                if not ReferralCode.objects.filter(
                    code=candidate
                ).exists():
                    self.code = candidate
                    break

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - {self.code}"


class Referral(models.Model):
    referral_code = models.CharField(max_length=100)

    referral_offer = models.ForeignKey(
        ReferralOffer,
        on_delete=models.CASCADE,
        related_name="referrals",
    )

    referrer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="referrals_sent",
    )

    referred_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="referrals_received",
    )

    reward_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    rewarded_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.referral_code
