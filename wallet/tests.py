from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from datetime import timedelta
from unittest.mock import patch
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone
from accounts.models import User
from accounts.models import User
from wallet.models import Wallet, WalletTransaction
from wallet.services.transaction_service import (
    process_wallet_transaction,
)
from wallet.services.refund_service import credit_wallet_refund


class WalletTransactionServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="wallet_test_user",
            email="wallet-test@example.com",
            password="Test-password-123",
        )

        self.wallet = Wallet.objects.create(
            user=self.user,
            balance=Decimal("100.00"),
            is_active=True,
        )

    def test_credit_increases_wallet_balance(self):
        wallet_transaction = process_wallet_transaction(
            wallet_id=self.wallet.pk,
            amount=Decimal("25.00"),
            transaction_type="credit",
            transaction_id="TEST-CREDIT-001",
            reference_id="TEST-ORDER-001",
        )

        self.wallet.refresh_from_db()

        self.assertEqual(self.wallet.balance, Decimal("125.00"))
        self.assertEqual(
            wallet_transaction.balance_after,
            Decimal("125.00"),
        )
        self.assertEqual(wallet_transaction.transaction_type, "credit")

    def test_debit_decreases_wallet_balance(self):
        wallet_transaction = process_wallet_transaction(
            wallet_id=self.wallet.pk,
            amount=Decimal("30.00"),
            transaction_type="debit",
            transaction_id="TEST-DEBIT-001",
            reference_id="TEST-ORDER-002",
        )

        self.wallet.refresh_from_db()

        self.assertEqual(self.wallet.balance, Decimal("70.00"))
        self.assertEqual(
            wallet_transaction.balance_after,
            Decimal("70.00"),
        )

    def test_insufficient_balance_is_rejected(self):
        with self.assertRaisesMessage(
            ValidationError,
            "Insufficient wallet balance.",
        ):
            process_wallet_transaction(
                wallet_id=self.wallet.pk,
                amount=Decimal("150.00"),
                transaction_type="debit",
                transaction_id="TEST-DEBIT-002",
                reference_id="TEST-ORDER-003",
            )

        self.wallet.refresh_from_db()

        self.assertEqual(self.wallet.balance, Decimal("100.00"))
        self.assertEqual(
            WalletTransaction.objects.filter(
                wallet=self.wallet
            ).count(),
            0,
        )

    def test_duplicate_transaction_is_rejected(self):
        process_wallet_transaction(
            wallet_id=self.wallet.pk,
            amount=Decimal("20.00"),
            transaction_type="credit",
            transaction_id="TEST-DUPLICATE-001",
            reference_id="TEST-ORDER-004",
        )

        with self.assertRaisesMessage(
            ValidationError,
            "This transaction has already been processed.",
        ):
            process_wallet_transaction(
                wallet_id=self.wallet.pk,
                amount=Decimal("20.00"),
                transaction_type="credit",
                transaction_id="TEST-DUPLICATE-001",
                reference_id="TEST-ORDER-004",
            )

        self.wallet.refresh_from_db()

        self.assertEqual(self.wallet.balance, Decimal("120.00"))
        self.assertEqual(
            WalletTransaction.objects.filter(
                wallet=self.wallet,
                transaction_id="TEST-DUPLICATE-001",
            ).count(),
            1,
        )

    def test_refund_credits_existing_wallet(self):
        wallet_transaction = credit_wallet_refund(
            user=self.user,
            amount=Decimal("25.00"),
            transaction_id="TEST-REFUND-001",
            reference_id="TEST-RETURN-001",
        )

        self.wallet.refresh_from_db()

        self.assertEqual(self.wallet.balance, Decimal("125.00"))
        self.assertEqual(wallet_transaction.amount, Decimal("25.00"))
        self.assertEqual(wallet_transaction.transaction_type, "credit")
        self.assertEqual(
            wallet_transaction.reference_id,
            "TEST-RETURN-001",
        )

    def test_refund_creates_wallet_for_user_without_one(self):
        refund_user = User.objects.create_user(
            username="refund_test_user",
            email="refund-test@example.com",
            password="Test-password-123",
        )

        wallet_transaction = credit_wallet_refund(
            user=refund_user,
            amount=Decimal("40.00"),
            transaction_id="TEST-REFUND-002",
            reference_id="TEST-RETURN-002",
        )

        refund_wallet = Wallet.objects.get(user=refund_user)

        self.assertEqual(refund_wallet.balance, Decimal("40.00"))
        self.assertEqual(wallet_transaction.wallet_id, refund_wallet.pk)

    def test_refund_rejects_inactive_wallet(self):
        self.wallet.is_active = False
        self.wallet.save(update_fields=["is_active"])

        with self.assertRaisesMessage(
            ValidationError,
            "The customer's wallet is inactive. "
            "The refund was not processed.",
        ):
            credit_wallet_refund(
                user=self.user,
                amount=Decimal("25.00"),
                transaction_id="TEST-REFUND-003",
                reference_id="TEST-RETURN-003",
            )

        self.wallet.refresh_from_db()

        self.assertEqual(self.wallet.balance, Decimal("100.00"))
        self.assertEqual(
            WalletTransaction.objects.filter(
                wallet=self.wallet
            ).count(),
            0,
        )

    def test_duplicate_refund_is_rejected(self):
        credit_wallet_refund(
            user=self.user,
            amount=Decimal("15.00"),
            transaction_id="TEST-REFUND-DUPLICATE",
            reference_id="TEST-RETURN-004",
        )

        with self.assertRaisesMessage(
            ValidationError,
            "This transaction has already been processed.",
        ):
            credit_wallet_refund(
                user=self.user,
                amount=Decimal("15.00"),
                transaction_id="TEST-REFUND-DUPLICATE",
                reference_id="TEST-RETURN-004",
            )

        self.wallet.refresh_from_db()

        self.assertEqual(self.wallet.balance, Decimal("115.00"))
        self.assertEqual(
            WalletTransaction.objects.filter(
                wallet=self.wallet,
                transaction_id="TEST-REFUND-DUPLICATE",
            ).count(),
            1,
        )



class WalletPageViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="wallet_page_user",
            email="wallet-page@example.com",
            password="Test-password-123",
        )

        self.wallet = Wallet.objects.create(
            user=self.user,
            balance=Decimal("100.00"),
            is_active=True,
        )

    def test_wallet_page_requires_login(self):
        response = self.client.get(reverse("wallet"))

        self.assertEqual(response.status_code, 302)

    def test_wallet_page_shows_own_wallet_and_newest_transactions(self):
        # Create two transactions for the current customer's wallet.
        older_transaction = WalletTransaction.objects.create(
            wallet=self.wallet,
            amount=Decimal("10.00"),
            balance_after=Decimal("90.00"),
            transaction_id="WALLET-PAGE-OLD",
            transaction_type="debit",
            reference_id="ORDER-OLD",
        )

        newer_transaction = WalletTransaction.objects.create(
            wallet=self.wallet,
            amount=Decimal("20.00"),
            balance_after=Decimal("110.00"),
            transaction_id="WALLET-PAGE-NEW",
            transaction_type="credit",
            reference_id="ORDER-NEW",
        )

        # Set explicit timestamps so the ordering test is deterministic.
        now = timezone.now()

        WalletTransaction.objects.filter(
            pk=older_transaction.pk
        ).update(created_at=now - timedelta(minutes=2))

        WalletTransaction.objects.filter(
            pk=newer_transaction.pk
        ).update(created_at=now - timedelta(minutes=1))

        # Create another customer's wallet and transaction.
        other_user = User.objects.create_user(
            username="another_wallet_user",
            email="another-wallet@example.com",
            password="Test-password-123",
        )

        other_wallet = Wallet.objects.create(
            user=other_user,
            balance=Decimal("500.00"),
            is_active=True,
        )

        other_transaction = WalletTransaction.objects.create(
            wallet=other_wallet,
            amount=Decimal("500.00"),
            balance_after=Decimal("500.00"),
            transaction_id="OTHER-WALLET-TRANSACTION",
            transaction_type="credit",
            reference_id="OTHER-ORDER",
        )

        self.client.force_login(self.user)

        # Mock rendering so this backend test doesn't depend on the template.
        with patch(
            "wallet.views.userside.wallet_view.render",
            return_value=HttpResponse("Wallet page"),
        ) as mocked_render:
            response = self.client.get(reverse("wallet"))

        self.assertEqual(response.status_code, 200)

        context = mocked_render.call_args.args[2]

        self.assertEqual(context["wallet"].pk, self.wallet.pk)

        transactions = list(context["transactions"])

        self.assertEqual(
            [item.pk for item in transactions],
            [newer_transaction.pk, older_transaction.pk],
        )

        self.assertNotIn(other_transaction.pk, [
            item.pk for item in transactions
        ])

    def test_wallet_page_handles_missing_wallet(self):
        self.client.force_login(self.user)

        self.wallet.delete()

        with patch(
            "wallet.views.userside.wallet_view.render",
            return_value=HttpResponse("Wallet page"),
        ) as mocked_render:
            response = self.client.get(reverse("wallet"))

        self.assertEqual(response.status_code, 200)

        context = mocked_render.call_args.args[2]

        self.assertIsNone(context["wallet"])
        self.assertEqual(list(context["transactions"]), [])
