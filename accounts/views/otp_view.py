
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache

from ..models import User
from ..services.otp_service import generate_otp, get_otp_expiry
from ..services.email_service import send_otp_email

from referrals.models import ReferralCode, Referral, ReferralOffer
from wallet.models import Wallet
from wallet.services.transaction_service import process_wallet_transaction


# Check whether the frontend expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Return an OTP workflow error without losing the signup session.
def otp_error(request, message, status=400):
    if wants_json(request):
        return JsonResponse({
            "success": False,
            "message": message,
        }, status=status)

    messages.error(request, message)
    return redirect("verify_otp")


# Verify the signup OTP and create the customer's account.
@never_cache
def verify_otp(request):

    # Prevent an already logged-in customer from repeating signup.
    if request.user.is_authenticated:
        if wants_json(request):
            return JsonResponse({
                "success": True,
                "message": "You are already logged in.",
                "redirect_url": reverse("home"),
            }, status=200)

        return redirect("home")

    # Allow OTP verification only through GET and POST requests.
    if request.method not in ["GET", "POST"]:
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "Only GET and POST requests are allowed.",
            }, status=405)

        return HttpResponseNotAllowed(["GET", "POST"])

    if request.method == "POST":
        entered_otp = request.POST.get("otp", "").strip()

        stored_otp = request.session.get("signup_otp")
        stored_expiry = request.session.get("signup_otp_expiry")
        signup_data = request.session.get("signup_data")

        # Check whether the signup session still exists.
        if not stored_otp or not signup_data:
            if wants_json(request):
                return JsonResponse({
                    "success": False,
                    "message": "Signup session has expired.",
                    "redirect_url": reverse("signup"),
                }, status=410)

            messages.error(request, "Signup session has expired.")
            return redirect("signup")

        # Check whether the OTP expiry time exists.
        if not stored_expiry:
            if wants_json(request):
                return JsonResponse({
                    "success": False,
                    "message": "OTP has expired.",
                    "redirect_url": reverse("signup"),
                }, status=410)

            messages.error(request, "OTP has expired.")
            return redirect("signup")

        # Convert the stored expiry string into a datetime object.
        expiry_time = datetime.fromisoformat(stored_expiry)

        # Reject an OTP that has passed its expiry time.
        if timezone.now() > expiry_time:
            if wants_json(request):
                return JsonResponse({
                    "success": False,
                    "message": "OTP has expired. Please request a new OTP.",
                }, status=410)

            messages.error(
                request,
                "OTP has expired. Please request a new OTP."
            )
            return redirect("verify_otp")

        # Reject an empty OTP.
        if not entered_otp:
            if wants_json(request):
                return JsonResponse({
                    "success": False,
                    "message": "Please enter the OTP.",
                }, status=400)

            messages.error(request, "Please enter the OTP.")

        # Verify the OTP entered by the customer.
        elif entered_otp == stored_otp:

            referral_code_text = request.session.get(
                "signup_referral_code"
            )
            referral_code_record = None
            referral_offer = None

            # Validate a stored referral before creating the account.
            if referral_code_text:
                referral_code_record = (
                    ReferralCode.objects.select_related("user")
                    .filter(code__iexact=referral_code_text)
                    .first()
                )

                if referral_code_record is None:
                    request.session.pop(
                        "signup_referral_code",
                        None,
                    )
                    return otp_error(
                        request,
                        "The referral code is no longer valid. "
                        "The referral has been removed; submit your OTP "
                        "again to continue without it.",
                    )

                # Prevent referrals to the same email account.
                if (
                    referral_code_record.user.email.casefold()
                    == signup_data["email"].casefold()
                ):
                    request.session.pop(
                        "signup_referral_code",
                        None,
                    )
                    return otp_error(
                        request,
                        "You cannot use your own referral code. "
                        "The referral has been removed; submit your OTP "
                        "again to continue.",
                    )

                # This model has no active flag, so use the most
                # recently created referral offer.
                referral_offer = (
                    ReferralOffer.objects.order_by("-created_at")
                    .first()
                )

                if referral_offer is None:
                    request.session.pop(
                        "signup_referral_code",
                        None,
                    )
                    return otp_error(
                        request,
                        "No referral reward is configured. "
                        "The referral has been removed; submit your OTP "
                        "again to complete signup.",
                    )

                if referral_offer.reward_amount <= Decimal("0.00"):
                    request.session.pop(
                        "signup_referral_code",
                        None,
                    )
                    return otp_error(
                        request,
                        "The referral reward is not configured correctly. "
                        "The referral has been removed; submit your OTP "
                        "again to complete signup.",
                    )

            try:
                # Create the account, wallet, referral record, and reward
                # in one database transaction.
                with transaction.atomic():

                    user = User(
                        username=signup_data["username"],
                        email=signup_data["email"],
                        phone=signup_data["phone"],
                        password=signup_data["password_hash"],
                    )
                    user.save()

                    # Create a wallet for the new customer.
                    Wallet.objects.get_or_create(
                        user=user,
                        defaults={
                            "balance": Decimal("0.00"),
                            "is_active": True,
                        },
                    )

                    if referral_code_record and referral_offer:
                        # Snapshot the offer amount on the referral record.
                        referral = Referral.objects.create(
                            referral_code=referral_code_record.code,
                            referral_offer=referral_offer,
                            referrer=referral_code_record.user,
                            referred_user=user,
                            reward_amount=referral_offer.reward_amount,
                        )

                        # Ensure the referrer has a wallet.
                        referrer_wallet, _ = Wallet.objects.get_or_create(
                            user=referral_code_record.user,
                            defaults={
                                "balance": Decimal("0.00"),
                                "is_active": True,
                            },
                        )

                        # Credit the referrer exactly once using a stable ID.
                        process_wallet_transaction(
                            wallet_id=referrer_wallet.pk,
                            amount=referral.reward_amount,
                            transaction_type="credit",
                            transaction_id=(
                                f"REFERRAL-{referral.pk}-REFERRER"
                            ),
                            reference_id=f"REFERRAL-{referral.pk}",
                        )

                        # Record that the reward has been credited.
                        referral.rewarded_at = timezone.now()
                        referral.save(
                            update_fields=["rewarded_at"]
                        )

            except ValidationError as error:
                error_message = (
                    error.messages[0]
                    if error.messages
                    else "The referral reward could not be processed."
                )
                return otp_error(request, error_message)

            # Clear temporary signup data after successful creation.
            request.session.pop("signup_otp", None)
            request.session.pop("signup_otp_expiry", None)
            request.session.pop("last_otp_resend", None)
            request.session.pop("signup_data", None)
            request.session.pop("signup_referral_code", None)

            if wants_json(request):
                return JsonResponse({
                    "success": True,
                    "message": "Account created successfully.",
                    "redirect_url": reverse("login"),
                }, status=201)

            messages.success(request, "Account created successfully.")
            return redirect("login")

        # Return an error when the OTP does not match.
        else:
            if wants_json(request):
                return JsonResponse({
                    "success": False,
                    "message": "Invalid OTP.",
                }, status=400)

            messages.error(request, "Invalid OTP.")

    # Calculate the remaining OTP validity time for the template.
    stored_expiry = request.session.get("signup_otp_expiry")
    remaining_seconds = 0

    if stored_expiry:
        expiry_time = datetime.fromisoformat(stored_expiry)
        remaining_seconds = max(
            0,
            int((expiry_time - timezone.now()).total_seconds())
        )

    return render(
        request,
        "accounts/verify_otp.html",
        {"remaining_seconds": remaining_seconds},
    )


# Resend a signup OTP while enforcing the 30-second cooldown.
@never_cache
def resend_otp(request):

    # Allow OTP resend only through POST requests.
    if request.method != "POST":
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "Only POST requests are allowed.",
            }, status=405)

        return HttpResponseNotAllowed(["POST"])

    signup_data = request.session.get("signup_data")

    # Check whether the signup session still exists.
    if not signup_data:
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "Signup session has expired.",
                "redirect_url": reverse("signup"),
            }, status=410)

        messages.error(request, "Signup session has expired.")
        return redirect("signup")

    # Check when the last OTP was requested.
    last_resend = request.session.get("last_otp_resend")

    if last_resend:
        last_resend_time = datetime.fromisoformat(last_resend)
        time_passed = timezone.now() - last_resend_time

        # Enforce the 30-second resend cooldown.
        if time_passed < timedelta(seconds=30):
            retry_after = max(
                1,
                30 - int(time_passed.total_seconds())
            )

            if wants_json(request):
                response = JsonResponse({
                    "success": False,
                    "message": "Please wait before requesting another OTP.",
                    "retry_after": retry_after,
                }, status=429)
                response["Retry-After"] = str(retry_after)
                return response

            messages.error(
                request,
                "Please wait 30 seconds before requesting another OTP."
            )
            return redirect("verify_otp")

    # Record the time of this OTP request.
    request.session["last_otp_resend"] = timezone.now().isoformat()

    # Generate a new OTP and its expiry time.
    otp = generate_otp()
    otp_expiry = get_otp_expiry()

    request.session["signup_otp"] = otp
    request.session["signup_otp_expiry"] = otp_expiry.isoformat()

    # Send the new OTP to the email address used during signup.
    send_otp_email(signup_data["email"], otp)

    if wants_json(request):
        return JsonResponse({
            "success": True,
            "message": "A new OTP has been sent.",
            "remaining_seconds": max(
                0,
                int((otp_expiry - timezone.now()).total_seconds())
            ),
        }, status=200)

    messages.success(request, "A new OTP has been sent.")
    return redirect("verify_otp")
