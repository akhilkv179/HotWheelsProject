
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase
from django.utils import timezone
from django.contrib.sessions.middleware import SessionMiddleware

from accounts.models import User
from accounts.views.otp_view import verify_otp
from wallet.models import Wallet


class SignupWalletCreationTests(TestCase):
    def test_successful_otp_verification_creates_wallet(self):
        factory = RequestFactory()

        request = factory.post(
            "/verify-otp/",
            {"otp": "123456"},
            HTTP_ACCEPT="application/json",
        )

        # Attach a session and an anonymous user to the test request.
        SessionMiddleware(lambda req: None).process_request(request)
        request.user = AnonymousUser()

        request.session["signup_otp"] = "123456"
        request.session["signup_otp_expiry"] = (
            timezone.now() + timedelta(minutes=5)
        ).isoformat()

        request.session["signup_data"] = {
            "username": "otp_wallet_test",
            "email": "otp-wallet-test@example.com",
            "phone": "9876543210",
            "password_hash": make_password("Test-password-123"),
        }

        response = verify_otp(request)

        self.assertEqual(response.status_code, 201)

        user = User.objects.get(username="otp_wallet_test")
        wallet = Wallet.objects.get(user=user)

        self.assertEqual(wallet.balance, Decimal("0.00"))
        self.assertTrue(wallet.is_active)

        # Signup session data should be cleared after success.
        self.assertNotIn("signup_otp", request.session)
        self.assertNotIn("signup_data", request.session)
