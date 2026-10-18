from datetime import datetime

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.cache import never_cache

from ..forms import ResetPasswordForm
from ..models import User


@never_cache
def verify_reset_otp(request):
    if request.method == "POST":
        entered_otp = request.POST.get("otp", "").strip()

        stored_otp = request.session.get("reset_otp")

        if not stored_otp:
            messages.error(
                request,
                "OTP session has expired. Please request a new OTP.",
            )
            return redirect("forgot_password")

        stored_expiry = request.session.get("reset_otp_expiry")

        expiry_time = datetime.fromisoformat(stored_expiry)

        if timezone.now() > expiry_time:
            messages.error(
                request,
                "OTP has expired. Please request a new OTP.",
            )
            return redirect("forgot_password")

        if entered_otp != stored_otp:
            messages.error(request, "Invalid OTP.")
            return render(
                request,
                "accounts/verify_reset_otp.html",
            )

        request.session["reset_otp_verified"] = True
        return redirect("reset_password")

    return render(request, "accounts/verify_reset_otp.html")


@never_cache
def reset_password(request):
    # The user must verify the OTP before resetting the password.
    if not request.session.get("reset_otp_verified"):
        messages.error(request, "Please verify the OTP first.")
        return redirect("forgot_password")

    if request.method == "POST":
        form = ResetPasswordForm(request.POST)

        if form.is_valid():
            new_password = form.cleaned_data["new_password"]
            reset_email = request.session.get("reset_email")

            user = User.objects.filter(
                email=reset_email,
            ).first()

            if user is None:
                messages.error(
                    request,
                    "Account not found. Please request a new password reset.",
                )
                return redirect("forgot_password")

            # Save the new password securely using Django's password hashing.
            user.set_password(new_password)
            user.save()

            # Clear the password-reset session data after success.
            request.session.pop("reset_email", None)
            request.session.pop("reset_otp", None)
            request.session.pop("reset_otp_expiry", None)
            request.session.pop("reset_otp_verified", None)

            messages.success(
                request,
                "Password reset successfully. Please login.",
            )
            return redirect("login")

        # Display form validation errors through Django messages.
        errors = []
        for field_errors in form.errors.values():
            errors.extend(field_errors)

        for error in dict.fromkeys(errors):
            messages.error(request, error)

    else:
        form = ResetPasswordForm()

    return render(
        request,
        "accounts/reset_password.html",
        {"form": form},
    )