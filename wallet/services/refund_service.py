
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from wallet.models import Wallet
from wallet.services.transaction_service import process_wallet_transaction


@transaction.atomic
def credit_wallet_refund(user, amount, transaction_id, reference_id):
    """Credit a refund to the user's active wallet."""

    wallet, created = Wallet.objects.get_or_create(
        user=user,
        defaults={
            "balance": Decimal("0.00"),
            "is_active": True,
        },
    )

    if not wallet.is_active:
        raise ValidationError(
            "The customer's wallet is inactive. The refund was not processed."
        )

    return process_wallet_transaction(
        wallet_id=wallet.pk,
        amount=amount,
        transaction_type="credit",
        transaction_id=transaction_id,
        reference_id=reference_id,
    )
