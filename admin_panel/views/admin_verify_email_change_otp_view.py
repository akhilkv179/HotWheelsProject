
from datetime import datetime

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from accounts.models import User


# Verify the OTP sent to the new admin email address.
@never_cache
@require_http_methods(["GET", "POST"])
def admin_verify_email_change_otp_view(request):

    # Check whether the admin is authenticated.
    if not request.user.is_authenticated:
        if request.method == "POST":
            return JsonResponse(
                {
                    "success": False,
                    "message": "Authentication required.",
                    "redirect_url": reverse("admin_login"),
                },
                status=401,
            )

        return redirect("admin_login")

    # Only active staff members can verify their email.
    if not request.user.is_active or not request.user.is_staff:
        if request.method == "POST":
            return JsonResponse(
                {
                    "success": False,
                    "message": "You do not have admin access.",
                },
                status=403,
            )

        return redirect("admin_login")

    # Retrieve the admin email verification session.
    new_email = request.session.get(
        "admin_email_change_new_email"
    )
    stored_otp = request.session.get(
        "admin_email_change_otp"
    )
    expiry_string = request.session.get(
        "admin_email_change_otp_expiry"
    )

    # Check whether the verification session is available.
    if not new_email or not stored_otp or not expiry_string:

        if request.method == "POST":
            return JsonResponse(
                {
                    "success": False,
                    "message": "Email verification session has expired.",
                    "redirect_url": reverse("admin_edit_profile"),
                },
                status=410,
            )

        messages.error(
            request,
            "Email verification session has expired."
        )
        return redirect("admin_edit_profile")

    expiry = datetime.fromisoformat(expiry_string)

    if request.method == "POST":

        entered_otp = request.POST.get("otp", "").strip()

        # Check whether the admin entered an OTP.
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
                    "redirect_url": reverse("admin_edit_profile"),
                },
                status=410,
            )

        # Check whether the entered OTP matches.
        if entered_otp != stored_otp:
            return JsonResponse(
                {
                    "success": False,
                    "message": "Invalid OTP.",
                },
                status=400,
            )

        user = request.user

        # Check whether another account already uses this email.
        email_exists = User.objects.filter(
            email__iexact=new_email
        ).exclude(
            id=user.id
        ).exists()

        if email_exists:

            request.session.pop(
                "admin_email_change_new_email", None
            )
            request.session.pop(
                "admin_email_change_otp", None
            )
            request.session.pop(
                "admin_email_change_otp_expiry", None
            )

            return JsonResponse(
                {
                    "success": False,
                    "message": "This email is already registered.",
                    "redirect_url": reverse("admin_edit_profile"),
                },
                status=409,
            )

        # Update the admin email after successful verification.
        user.email = new_email
        user.save()

        # Clear the admin email verification session.
        request.session.pop(
            "admin_email_change_new_email", None
        )
        request.session.pop(
            "admin_email_change_otp", None
        )
        request.session.pop(
            "admin_email_change_otp_expiry", None
        )

        return JsonResponse(
            {
                "success": True,
                "message": "Admin email updated successfully.",
                "redirect_url": reverse("admin_profile"),
            },
            status=200,
        )

    # Display the admin OTP verification page.
    return render(
        request,
        "admin_panel/admin_verify_email_change_otp.html",
    )
