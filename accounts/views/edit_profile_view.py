from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.views.decorators.cache import never_cache

from ..forms import ProfileForm
from ..services.otp_service import generate_otp, get_otp_expiry
from ..services.email_service import send_otp_email


@never_cache
@login_required
def edit_profile(request):
    """Validate profile fields and handle email-change verification."""

    user = request.user

    if request.method == "POST":
        form = ProfileForm(
            request.POST,
            user=user,
        )

        if form.is_valid():
            data = form.cleaned_data

            username = data["username"]
            phone = data["phone"]
            email = data["email"]

            # If the email changes, verify the new email using OTP.
            if email.lower() != user.email.lower():
                otp = generate_otp()
                expiry = get_otp_expiry()

                request.session["email_change_new_email"] = email
                request.session["email_change_otp"] = otp
                request.session["email_change_otp_expiry"] = (
                    expiry.isoformat()
                )

                send_otp_email(email, otp)

                # Preserve the existing behaviour: update these fields
                # before redirecting to email verification.
                user.username = username
                user.phone = phone
                user.save()

                messages.success(
                    request,
                    "OTP has been sent to your new email address.",
                )

                return redirect("verify_email_change_otp")

            # Update the profile directly if the email is unchanged.
            user.username = username
            user.phone = phone
            user.save()

            messages.success(
                request,
                "Profile updated successfully.",
            )

            return redirect("profile")

        # Preserve the existing messages-based error handling.
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)

    else:
        # Pre-fill the form with the user's current details.
        form = ProfileForm(
            initial={
                "username": user.username,
                "phone": user.phone,
                "email": user.email,
            },
            user=user,
        )

    return render(
        request,
        "accounts/edit_profile.html",
        {
            "form": form,
            "user": user,
        },
    )