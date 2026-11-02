from datetime import datetime, timedelta

from django.contrib import messages
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache

from accounts.services.otp_service import generate_otp, get_otp_expiry
from accounts.services.email_service import send_otp_email


def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Resend the OTP for changing the admin password.
@never_cache
def admin_resend_password_change_otp_view(request):

    # Check whether the admin is logged in.
    if not request.user.is_authenticated:
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "Authentication required.",
                "redirect_url": reverse("admin_login"),
            }, status=401)

        return redirect("admin_login")

    # Check admin permissions.
    if not request.user.is_active or not request.user.is_staff:
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "You do not have admin access.",
            }, status=403)

        return redirect("admin_login")

    # Allow only POST requests.
    if request.method != "POST":
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "Only POST requests are allowed.",
            }, status=405)

        return HttpResponseNotAllowed(["POST"])

    user = request.user

    # Check whether the previous OTP session exists.
    if not request.session.get("admin_password_change_otp"):
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "OTP session has expired. Please request a new OTP.",
                "redirect_url": reverse("admin_change_password"),
            }, status=410)

        messages.error(request, "OTP session has expired.")
        return redirect("admin_change_password")

    # Check when the last OTP was requested.
    last_resend = request.session.get(
        "admin_password_change_last_otp_resend"
    )

    if last_resend:
        try:
            last_resend_time = datetime.fromisoformat(last_resend)
        except (ValueError, TypeError):
            last_resend_time = None

        if last_resend_time:
            time_passed = timezone.now() - last_resend_time

            # Enforce the 30-second cooldown.
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

                return redirect("admin_verify_password_change_otp")

    # Generate a new OTP and its expiry time.
    otp = generate_otp()
    otp_expiry = get_otp_expiry()

    # Update the admin session.
    request.session["admin_password_change_otp"] = otp
    request.session["admin_password_change_otp_expiry"] = (
        otp_expiry.isoformat()
    )

    request.session["admin_password_change_last_otp_resend"] = (
        timezone.now().isoformat()
    )

    # Clear any previous verification status.
    request.session.pop("admin_password_change_verified", None)

    # Send the new OTP to the admin's registered email.
    send_otp_email(user.email, otp)

    if wants_json(request):
        return JsonResponse({
            "success": True,
            "message": "A new OTP has been sent to your registered email.",
            "remaining_seconds": max(
                0,
                int((otp_expiry - timezone.now()).total_seconds())
            ),
        }, status=200)

    messages.success(
        request,
        "A new OTP has been sent to your registered email."
    )

    return redirect("admin_verify_password_change_otp")