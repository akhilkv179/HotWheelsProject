
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from wallet.models import Wallet, WalletTransaction


@transaction.atomic
def process_wallet_transaction(
    wallet_id,
    amount,
    transaction_type,
    transaction_id,
    reference_id,
):
    try:
        amount = Decimal(str(amount))
    except (ValueError, TypeError, ArithmeticError):
        raise ValidationError("Invalid transaction amount.")

    if not amount.is_finite() or amount <= Decimal("0.00"):
        raise ValidationError(
            "Transaction amount must be greater than zero."
        )

    if not transaction_type or not transaction_id or not reference_id:
        raise ValidationError("Transaction details are required.")

    try:
        wallet = Wallet.objects.select_for_update().get(
            pk=wallet_id,
            is_active=True,
        )
    except Wallet.DoesNotExist:
        raise ValidationError("Active wallet not found.")

    if WalletTransaction.objects.filter(
        wallet=wallet,
        transaction_id=transaction_id,
    ).exists():
        raise ValidationError(
            "This transaction has already been processed."
        )

    if transaction_type == "credit":
        new_balance = wallet.balance + amount

    elif transaction_type == "debit":
        if wallet.balance < amount:
            raise ValidationError("Insufficient wallet balance.")

        new_balance = wallet.balance - amount

    else:
        raise ValidationError(
            "Transaction type must be credit or debit."
        )

    # Create the transaction first. The nested atomic block allows
    # a uniqueness violation to be handled safely.
    try:
        with transaction.atomic():
            wallet_transaction = WalletTransaction.objects.create(
                wallet=wallet,
                amount=amount,
                balance_after=new_balance,
                transaction_id=transaction_id,
                transaction_type=transaction_type,
                reference_id=reference_id,
            )
    except IntegrityError:
        raise ValidationError(
            "This transaction has already been processed."
        )

    # Update the balance only after the transaction record succeeds.
    wallet.balance = new_balance
    wallet.save(update_fields=["balance", "updated_at"])

    return wallet_transaction
