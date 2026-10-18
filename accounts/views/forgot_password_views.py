from django.contrib import messages
from django.shortcuts import render, redirect
from django.views.decorators.cache import never_cache

from ..forms import ForgotPasswordForm
from ..models import User
from ..services.otp_service import generate_otp, get_otp_expiry
from ..services.email_service import send_otp_email


@never_cache
def forgot_password(request):
    """Validate the email and start the password-reset OTP process."""

    if request.method == "POST":
        form = ForgotPasswordForm(request.POST)

        if form.is_valid():
            email = form.cleaned_data["email"]

            # Find the account associated with this email.
            user = User.objects.filter(
                email__iexact=email
            ).first()

            if user is None:
                messages.error(
                    request,
                    "No account found with this email.",
                )
                return render(
                    request,
                    "accounts/forgot_password.html",
                    {"form": form},
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

            messages.success(
                request,
                "OTP has been sent to your email.",
            )

            return redirect("verify_reset_otp")

        # Display the form validation errors.
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)

    else:
        form = ForgotPasswordForm()

    return render(
        request,
        "accounts/forgot_password.html",
        {"form": form},
    )