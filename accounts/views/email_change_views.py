
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from ..models import User


# Verify the OTP sent to the new email address before updating user email.
@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def verify_email_change_otp(request):

    new_email = request.session.get("email_change_new_email")
    stored_otp = request.session.get("email_change_otp")
    expiry_string = request.session.get("email_change_otp_expiry")

    # Check whether the email verification session is available.
    if not new_email or not stored_otp or not expiry_string:
        if request.method == "POST":
            return JsonResponse(
                {
                    "success": False,
                    "message": "Email verification session has expired.",
                    "redirect_url": reverse("edit_profile"),
                },
                status=410,
            )

        messages.error(request, "Email verification session has expired.")
        return redirect("edit_profile")

    expiry = datetime.fromisoformat(expiry_string)

    if request.method == "POST":

        entered_otp = request.POST.get("otp", "").strip()

        # Check whether the user entered an OTP.
        if not entered_otp:
            return JsonResponse(
                {
                    "success": False,
                    "message": "OTP is required.",
                },
                status=400,
            )

        # Check whether the OTP has expired.
        if timezone.now() > expiry:
            return JsonResponse(
                {
                    "success": False,
                    "message": "OTP has expired.",
                    "redirect_url": reverse("edit_profile"),
                },
                status=410,
            )

        # Check whether the entered OTP matches the stored OTP.
        if entered_otp != stored_otp:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Invalid OTP.",
                },
                status=400,
            )

        user = request.user

        # Check whether another user already has this email address.
        email_exists = User.objects.filter(
            email__iexact=new_email
        ).exclude(
            id=user.id
        ).exists()

        if email_exists:
            request.session.pop("email_change_new_email", None)
            request.session.pop("email_change_otp", None)
            request.session.pop("email_change_otp_expiry", None)

            return JsonResponse(
                {
                    "success": False,
                    "message": "This email is already registered.",
                    "redirect_url": reverse("edit_profile"),
                },
                status=409,
            )

        # Update the user's email after successful OTP verification.
        user.email = new_email
        user.save()

        # Clear the email verification session after successful verification.
        request.session.pop("email_change_new_email", None)
        request.session.pop("email_change_otp", None)
        request.session.pop("email_change_otp_expiry", None)

        return JsonResponse(
            {
                "success": True,
                "message": "Email updated successfully.",
                "redirect_url": reverse("profile"),
            },
            status=200,
        )

    # Display the existing OTP verification page.
    return render(
        request,
        "accounts/verify_email_change_otp.html",
    )
