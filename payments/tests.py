
import hashlib
import hmac
import json
from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import RequestFactory, TestCase, override_settings

from accounts.models import User
from orders.models import Order, OrderStatusHistory
from payments.models import Payment
from payments.views.userside.create_razorpay_order_view import (
    create_razorpay_order,
)
from payments.views.userside.verify_razorpay_payment_view import (
    verify_razorpay_payment_view,
)
from payments.views.razorpay_webhook_view import razorpay_webhook_view
from wallet.models import Wallet


@override_settings(
    RAZORPAY_KEY_ID="rzp_test_example",
    RAZORPAY_KEY_SECRET="test_secret",
)
class RazorpayFlowTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        self.user = User.objects.create_user(
            username="razorpay_test_user",
            email="razorpay-test@example.com",
            password="Test-password-123",
        )

        self.order = Order.objects.create(
            user=self.user,
            address=None,
            order_number="HW-RAZORPAY-TEST",
            status="pending",
            subtotal=Decimal("100.00"),
            discount_amount=Decimal("0.00"),
            shipping_amount=Decimal("0.00"),
            total_amount=Decimal("100.00"),
            delivery_method="Razorpay",
        )

        self.razorpay_order_id = "order_test_123"
        self.razorpay_payment_id = "pay_test_123"

        self.payment = Payment.objects.create(
            order=self.order,
            amount=Decimal("100.00"),
            payment_method="razorpay",
            status="created",
            razorpay_order_id=self.razorpay_order_id,
            transaction_id="",
        )

    def create_signature(self):
        message = (
            f"{self.razorpay_order_id}|"
            f"{self.razorpay_payment_id}"
        )

        return hmac.new(
            b"test_secret",
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def make_verify_request(self, signature=None):
        payload = {
            "razorpay_order_id": self.razorpay_order_id,
            "razorpay_payment_id": self.razorpay_payment_id,
            "razorpay_signature": (
                signature or self.create_signature()
            ),
            "order_number": self.order.order_number,
        }

        request = self.factory.post(
            "/payments/verify-razorpay-payment/",
            data=json.dumps(payload),
            content_type="application/json",
        )
        request.user = self.user

        return request

    def test_create_razorpay_order(self):
        # Remove the existing payment so a new gateway order is created.
        self.payment.delete()

        client = Mock()
        client.order.create.return_value = {
            "id": "order_gateway_456",
        }

        with patch(
            "payments.views.userside.create_razorpay_order_view.razorpay.Client",
            return_value=client,
        ):
            request = self.factory.post("/payments/create/")
            request.user = self.user

            response = create_razorpay_order(
                request,
                order_number=self.order.order_number,
            )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)

        self.assertEqual(
            data["razorpay_order_id"],
            "order_gateway_456",
        )
        self.assertEqual(data["amount"], 10000)
        self.assertEqual(data["currency"], "INR")

        self.assertTrue(
            Payment.objects.filter(
                order=self.order,
                razorpay_order_id="order_gateway_456",
                status="created",
            ).exists()
        )

        client.order.create.assert_called_once()

    def test_existing_gateway_order_is_reused(self):
        with patch(
            "payments.views.userside.create_razorpay_order_view.razorpay.Client"
        ) as client_class:
            request = self.factory.post("/payments/create/")
            request.user = self.user

            response = create_razorpay_order(
                request,
                order_number=self.order.order_number,
            )

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)

        self.assertEqual(
            data["razorpay_order_id"],
            self.razorpay_order_id,
        )
        self.assertEqual(data["amount"], 10000)

        client_class.assert_not_called()

    def test_captured_payment_is_verified(self):
        client = Mock()
        client.payment.fetch.return_value = {
            "id": self.razorpay_payment_id,
            "order_id": self.razorpay_order_id,
            "amount": 10000,
            "currency": "INR",
            "status": "captured",
        }

        with patch(
            "payments.views.userside.verify_razorpay_payment_view.razorpay.Client",
            return_value=client,
        ):
            response = verify_razorpay_payment_view(
                self.make_verify_request()
            )

        self.assertEqual(response.status_code, 200)

        self.payment.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(self.payment.status, "paid")
        self.assertEqual(
            self.payment.transaction_id,
            self.razorpay_payment_id,
        )
        self.assertIsNotNone(self.payment.paid_at)
        self.assertEqual(self.order.status, "confirmed")

        self.assertTrue(
            OrderStatusHistory.objects.filter(
                order=self.order,
                status="confirmed",
            ).exists()
        )

    def test_invalid_signature_is_rejected(self):
        with patch(
            "payments.views.userside.verify_razorpay_payment_view.razorpay.Client"
        ) as client_class:
            response = verify_razorpay_payment_view(
                self.make_verify_request(
                    signature="invalid-signature"
                )
            )

        self.assertEqual(response.status_code, 400)
        client_class.assert_not_called()

        self.payment.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(self.payment.status, "created")
        self.assertEqual(self.order.status, "pending")

    def test_uncaptured_payment_is_not_confirmed(self):
        client = Mock()
        client.payment.fetch.return_value = {
            "id": self.razorpay_payment_id,
            "order_id": self.razorpay_order_id,
            "amount": 10000,
            "currency": "INR",
            "status": "authorized",
        }

        with patch(
            "payments.views.userside.verify_razorpay_payment_view.razorpay.Client",
            return_value=client,
        ):
            response = verify_razorpay_payment_view(
                self.make_verify_request()
            )

        self.assertEqual(response.status_code, 409)

        self.payment.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(self.payment.status, "created")
        self.assertEqual(self.order.status, "pending")

    def test_wrong_payment_amount_is_rejected(self):
        client = Mock()
        client.payment.fetch.return_value = {
            "id": self.razorpay_payment_id,
            "order_id": self.razorpay_order_id,
            "amount": 5000,
            "currency": "INR",
            "status": "captured",
        }

        with patch(
            "payments.views.userside.verify_razorpay_payment_view.razorpay.Client",
            return_value=client,
        ):
            response = verify_razorpay_payment_view(
                self.make_verify_request()
            )

        self.assertEqual(response.status_code, 400)

        self.payment.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(self.payment.status, "created")
        self.assertEqual(self.order.status, "pending")

    def test_successful_verification_can_be_retried_safely(self):
        client = Mock()
        client.payment.fetch.return_value = {
            "id": self.razorpay_payment_id,
            "order_id": self.razorpay_order_id,
            "amount": 10000,
            "currency": "INR",
            "status": "captured",
        }

        with patch(
            "payments.views.userside.verify_razorpay_payment_view.razorpay.Client",
            return_value=client,
        ):
            first_response = verify_razorpay_payment_view(
                self.make_verify_request()
            )

            second_response = verify_razorpay_payment_view(
                self.make_verify_request()
            )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)

        self.assertEqual(
            Payment.objects.filter(
                order=self.order,
                status="paid",
            ).count(),
            1,
        )

        self.assertEqual(
            OrderStatusHistory.objects.filter(
                order=self.order,
                status="confirmed",
            ).count(),
            1,
        )



@override_settings(
    RAZORPAY_WEBHOOK_SECRET="webhook-test-secret",
)
class RazorpayWebhookTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        self.user = User.objects.create_user(
            username="webhook_test_user",
            email="webhook-test@example.com",
            password="Test-password-123",
        )

        self.order = Order.objects.create(
            user=self.user,
            address=None,
            order_number="HW-WEBHOOK-TEST",
            status="pending",
            subtotal=Decimal("100.00"),
            discount_amount=Decimal("0.00"),
            shipping_amount=Decimal("0.00"),
            total_amount=Decimal("100.00"),
            delivery_method="Razorpay",
        )

        self.payment = Payment.objects.create(
            order=self.order,
            amount=Decimal("100.00"),
            payment_method="razorpay",
            status="created",
            razorpay_order_id="order_webhook_test",
            transaction_id="",
        )

    def make_event(self):
        return {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_webhook_test",
                        "order_id": "order_webhook_test",
                        "amount": 10000,
                        "currency": "INR",
                        "status": "captured",
                    }
                }
            },
        }

    def send_webhook(self, payload, signature_override=None):
        raw_body = json.dumps(payload).encode("utf-8")

        signature = hmac.new(
            b"webhook-test-secret",
            raw_body,
            hashlib.sha256,
        ).hexdigest()

        if signature_override is not None:
            signature = signature_override

        request = self.factory.post(
            "/payments/razorpay-webhook/",
            data=raw_body,
            content_type="application/json",
            HTTP_X_RAZORPAY_SIGNATURE=signature,
            HTTP_X_RAZORPAY_EVENT_ID="evt_webhook_test",
        )

        return razorpay_webhook_view(request)

    def test_captured_webhook_confirms_order(self):
        response = self.send_webhook(self.make_event())

        self.assertEqual(response.status_code, 200)

        self.payment.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(self.payment.status, "paid")
        self.assertEqual(
            self.payment.transaction_id,
            "pay_webhook_test",
        )
        self.assertEqual(self.order.status, "confirmed")

        self.assertEqual(
            OrderStatusHistory.objects.filter(
                order=self.order,
                status="confirmed",
            ).count(),
            1,
        )

    def test_invalid_webhook_signature_is_rejected(self):
        response = self.send_webhook(
            self.make_event(),
            signature_override="invalid-signature",
        )

        self.assertEqual(response.status_code, 400)

        self.payment.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(self.payment.status, "created")
        self.assertEqual(self.order.status, "pending")

    def test_duplicate_webhook_does_not_confirm_twice(self):
        first_response = self.send_webhook(self.make_event())
        second_response = self.send_webhook(self.make_event())

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)

        self.assertEqual(
            OrderStatusHistory.objects.filter(
                order=self.order,
                status="confirmed",
            ).count(),
            1,
        )

    def test_late_capture_for_cancelled_order_credits_wallet(self):
        self.order.status = "cancelled"
        self.order.save(update_fields=["status", "updated_at"])

        response = self.send_webhook(self.make_event())

        self.assertEqual(response.status_code, 200)

        self.payment.refresh_from_db()
        self.order.refresh_from_db()

        wallet = Wallet.objects.get(user=self.user)

        self.assertEqual(self.payment.status, "paid")
        self.assertEqual(self.order.status, "cancelled")
        self.assertEqual(wallet.balance, Decimal("100.00"))

        self.assertEqual(
            wallet.transactions.filter(
                transaction_id=(
                    f"RAZORPAY-CAPTURE-REFUND-{self.payment.pk}"
                ),
                transaction_type="credit",
            ).count(),
            1,
        )
