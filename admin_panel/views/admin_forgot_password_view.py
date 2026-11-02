from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache

from accounts.forms import ForgotPasswordForm
from accounts.models import User
from accounts.services.otp_service import generate_otp, get_otp_expiry
from accounts.services.email_service import send_otp_email


@never_cache
def admin_forgot_password_view(request):

    # Allow only GET and POST requests.
    if request.method not in ["GET", "POST"]:
        return JsonResponse({
            "success": False,
            "message": "Method not allowed."
        }, status=405)

    if request.method == "POST":

        form = ForgotPasswordForm(request.POST)

        if form.is_valid():

            email = form.cleaned_data["email"]

            # Find an active admin account using the submitted email.
            user = User.objects.filter(
                email__iexact=email,
                is_staff=True,
                is_active=True
            ).first()

            # Return a generic response to avoid revealing account existence.
            if user is None:
                return JsonResponse({
                    "success": True,
                    "message": "If an admin account exists with this email, an OTP has been sent."
                }, status=200)

            # Store the admin email in the session.
            request.session["admin_reset_email"] = user.email

            # Generate OTP and expiry time.
            otp = generate_otp()
            otp_expiry = get_otp_expiry()

            request.session["admin_reset_otp"] = otp
            request.session["admin_reset_otp_expiry"] = otp_expiry.isoformat()

            # Start the 30-second resend cooldown.
            request.session["admin_reset_last_otp_resend"] = timezone.now().isoformat()

            # Clear any previous OTP verification status.
            request.session.pop("admin_reset_otp_verified", None)

            # Send OTP to the admin's registered email.
            send_otp_email(user.email, otp)

            return JsonResponse({
                "success": True,
                "message": "If an admin account exists with this email, an OTP has been sent.",
                "redirect_url": reverse("admin_verify_forgot_password_otp")
            }, status=200)

        return JsonResponse({
            "success": False,
            "message": "Please enter a valid email address.",
            "errors": form.errors.get_json_data()
        }, status=400)

    # Display the forgot-password page.
    form = ForgotPasswordForm()

    return render(
        request,
        "admin_panel/admin_forgot_password.html",
        {"form": form}
    )