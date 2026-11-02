
from datetime import datetime, timedelta

from django.contrib import messages
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache

from accounts.services.otp_service import generate_otp, get_otp_expiry
from accounts.services.email_service import send_otp_email


# Check whether the frontend expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Resend the admin email-change OTP with a 30-second cooldown.
@never_cache
def admin_resend_email_change_otp_view(request):

    # Allow OTP resend only through POST requests.
    if request.method != "POST":
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "Only POST requests are allowed.",
            }, status=405)

        return HttpResponseNotAllowed(["POST"])

    # Check whether the admin is authenticated.
    if not request.user.is_authenticated:
        return JsonResponse({
            "success": False,
            "message": "Authentication required.",
            "redirect_url": reverse("admin_login"),
        }, status=401)

    # Only active staff members can resend the OTP.
    if not request.user.is_active or not request.user.is_staff:
        return JsonResponse({
            "success": False,
            "message": "You do not have admin access.",
        }, status=403)

    # Retrieve the new email address from the session.
    new_email = request.session.get(
        "admin_email_change_new_email"
    )

    if not new_email:
        return JsonResponse({
            "success": False,
            "message": "Email verification session has expired.",
            "redirect_url": reverse("admin_edit_profile"),
        }, status=410)

    # Check when the last OTP was requested.
    last_resend = request.session.get(
        "admin_email_change_last_otp_resend"
    )

    if last_resend:
        last_resend_time = datetime.fromisoformat(last_resend)
        time_passed = timezone.now() - last_resend_time

        # Enforce the 30-second resend cooldown.
        if time_passed < timedelta(seconds=30):

            retry_after = max(
                1,
                30 - int(time_passed.total_seconds())
            )

            response = JsonResponse({
                "success": False,
                "message": "Please wait before requesting another OTP.",
                "retry_after": retry_after,
            }, status=429)

            response["Retry-After"] = str(retry_after)
            return response

    # Generate a new OTP and expiry time.
    otp = generate_otp()
    otp_expiry = get_otp_expiry()

    # Update the admin email verification session.
    request.session["admin_email_change_otp"] = otp
    request.session["admin_email_change_otp_expiry"] = (
        otp_expiry.isoformat()
    )
    request.session["admin_email_change_last_otp_resend"] = (
        timezone.now().isoformat()
    )

    # Send the new OTP to the admin's new email address.
    send_otp_email(new_email, otp)

    return JsonResponse({
        "success": True,
        "message": "A new OTP has been sent.",
        "remaining_seconds": max(
            0,
            int((otp_expiry - timezone.now()).total_seconds())
        ),
    }, status=200)
