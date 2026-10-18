from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.cache import never_cache

from ..forms import SetNewPasswordForm
from ..services.otp_service import generate_otp, get_otp_expiry
from ..services.email_service import send_otp_email


@never_cache
@login_required
def change_password(request):
    """Send an OTP to the logged-in user's registered email."""

    user = request.user

    if request.method == "POST":
        otp = generate_otp()
        expiry = get_otp_expiry()

        request.session["password_change_otp"] = otp
        request.session["password_change_otp_expiry"] = expiry.isoformat()

        send_otp_email(user.email, otp)

        messages.success(
            request,
            "OTP has been sent to your registered email.",
        )
        return redirect("verify_password_change_otp")

    return render(request, "accounts/change_password.html")


@never_cache
def verify_password_change_otp(request):

    stored_otp = request.session.get("password_change_otp")
    expiry_string = request.session.get("password_change_otp_expiry")

    if not stored_otp or not expiry_string:
        messages.error(request, "OTP session has expired.")
        return redirect("change_password")

    expiry = datetime.fromisoformat(expiry_string)

    if request.method == "POST":
        entered_otp = request.POST.get("otp", "").strip()

        if not entered_otp:
            messages.error(request, "OTP is required")
            return render(
                request,
                "accounts/verify_password_change_otp.html",
            )

        if timezone.now() > expiry:
            messages.error(request, "OTP has expired")
            return render(
                request,
                "accounts/verify_password_change_otp.html",
            )

        if entered_otp != stored_otp:
            messages.error(request, "Invalid OTP")
            return render(
                request,
                "accounts/verify_password_change_otp.html",
            )

        request.session["password_change_verified"] = True

        request.session.pop("password_change_otp", None)
        request.session.pop("password_change_otp_expiry", None)

        return redirect("set_new_password")

    return render(
        request,
        "accounts/verify_password_change_otp.html",
    )


@never_cache
@login_required
def set_new_password(request):
    """Validate and save a new password after OTP verification."""

    if not request.session.get("password_change_verified"):
        messages.error(request, "Please verify the OTP first.")
        return redirect("change_password")

    user = request.user

    if request.method == "POST":
        form = SetNewPasswordForm(
            request.POST,
            user=user,
        )

        if form.is_valid():
            new_password = form.cleaned_data["new_password"]

            user.set_password(new_password)
            user.save()

            # Keep the current user logged in after changing the password.
            update_session_auth_hash(request, user)

            request.session.pop("password_change_verified", None)

            messages.success(
                request,
                "Password changed successfully.",
            )
            return redirect("profile")

        # Display validation errors using Django messages.
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)

    else:
        form = SetNewPasswordForm(user=user)

    return render(
        request,
        "accounts/set_new_password.html",
        {"form": form},
    )