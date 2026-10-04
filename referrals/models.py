from django.db import models

from accounts.models import User


class ReferralOffer(models.Model):
    reward_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Referral Offer - {self.reward_amount}"


class Referral(models.Model):
    referral_code = models.CharField(max_length=100)

    referral_offer = models.ForeignKey(
        ReferralOffer,
        on_delete=models.CASCADE,
        related_name="referrals"
    )

    referrer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="referrals_sent"
    )

    referred_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="referrals_received"
    )

    reward_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    rewarded_at = models.DateTimeField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.referral_code