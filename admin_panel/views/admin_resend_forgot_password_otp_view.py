from datetime import datetime

from django.http import JsonResponse, HttpResponseNotAllowed
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache

from accounts.models import User
from accounts.services.otp_service import generate_otp, get_otp_expiry
from accounts.services.email_service import send_otp_email


def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


@never_cache
def admin_resend_forgot_password_otp_view(request):

    # Allow only POST requests.
    if request.method != "POST":
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "Only POST requests are allowed."
            }, status=405)

        return HttpResponseNotAllowed(["POST"])

    # Get the email stored during the forgot-password process.
    email = request.session.get("admin_reset_email")

    if not email:
        return JsonResponse({
            "success": False,
            "message": "Password reset session expired. Please try again.",
            "redirect_url": reverse("admin_forgot_password")
        }, status=410)

    # Find the active admin account.
    user = User.objects.filter(
        email__iexact=email,
        is_staff=True,
        is_active=True
    ).first()

    if user is None:
        return JsonResponse({
            "success": False,
            "message": "Admin account not found.",
            "redirect_url": reverse("admin_forgot_password")
        }, status=404)

    # Check the 30-second resend cooldown.
    last_resend = request.session.get("admin_reset_last_otp_resend")

    if last_resend:
        last_resend_time = datetime.fromisoformat(last_resend)

        elapsed_seconds = (
            timezone.now() - last_resend_time
        ).total_seconds()

        remaining_seconds = 30 - int(elapsed_seconds)

        if remaining_seconds > 0:
            return JsonResponse({
                "success": False,
                "message": f"Please wait {remaining_seconds} seconds before requesting another OTP.",
                "retry_after": remaining_seconds
            }, status=429)

    # Generate a new OTP and expiry time.
    otp = generate_otp()
    otp_expiry = get_otp_expiry()

    request.session["admin_reset_otp"] = otp
    request.session["admin_reset_otp_expiry"] = otp_expiry.isoformat()
    request.session["admin_reset_last_otp_resend"] = timezone.now().isoformat()

    # Clear previous OTP verification status.
    request.session.pop("admin_reset_otp_verified", None)

    # Send the new OTP to the admin's email.
    send_otp_email(user.email, otp)

    return JsonResponse({
        "success": True,
        "message": "A new OTP has been sent to your registered email address."
    }, status=200)