
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.cache import never_cache

from ..forms import ForgotPasswordForm
from ..models import User
from ..services.otp_service import generate_otp, get_otp_expiry
from ..services.email_service import send_otp_email


# Process password recovery requests and send a verification OTP to the user.
@never_cache
def forgot_password(request):
    """Validate the email and start the password-reset OTP process."""

    # Return JSON for unsupported HTTP methods.
    if request.method not in ["GET", "POST"]:
        return JsonResponse(
            {
                "success": False,
                "message": "Method not allowed.",
            },
            status=405,
        )

    if request.method == "POST":
        form = ForgotPasswordForm(request.POST)

        if form.is_valid():
            email = form.cleaned_data["email"]

            # Find the account associated with this email.
            user = User.objects.filter(
                email__iexact=email
            ).first()

            # Use a generic response to avoid revealing registered emails.
            if user is None:
                return JsonResponse(
                    {
                        "success": True,
                        "message": (
                            "If an account exists with this email, "
                            "an OTP has been sent."
                        ),
                    },
                    status=200,
                )

            # Store the account email in the session.
            request.session["reset_email"] = user.email

            # Generate an OTP and its expiry time.
            otp = generate_otp()
            otp_expiry = get_otp_expiry()

            request.session["reset_otp"] = otp
            request.session["reset_otp_expiry"] = (
                otp_expiry.isoformat()
            )

            # Send the OTP to the registered email address.
            send_otp_email(user.email, otp)

            return JsonResponse(
                {
                    "success": True,
                    "message": (
                        "If an account exists with this email, "
                        "an OTP has been sent."
                    ),
                    "redirect_url": reverse("verify_reset_otp"),
                },
                status=200,
            )

        # Return form validation errors as JSON.
        return JsonResponse(
            {
                "success": False,
                "message": "Please enter a valid email address.",
                "errors": form.errors.get_json_data(),
            },
            status=400,
        )

    # Display the existing forgot password page.
    form = ForgotPasswordForm()

    return render(
        request,
        "accounts/forgot_password.html",
        {"form": form},
    )
