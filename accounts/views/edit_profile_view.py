
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from ..forms import ProfileForm
from ..services.otp_service import generate_otp, get_otp_expiry
from ..services.email_service import send_otp_email


# Update user profile information and send OTP if email is modified.
@never_cache
@login_required
@require_http_methods(["GET", "POST"])
def edit_profile(request):
    

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
                # before email verification.
                user.username = username
                user.phone = phone
                user.save()

                return JsonResponse(
                    {
                        "success": True,
                        "message": (
                            "OTP has been sent to your new email address."
                        ),
                        "redirect_url": "/verify-email-change-otp/",
                        "requires_otp": True,
                    },
                    status=200,
                )

            # Update the profile directly if the email is unchanged.
            user.username = username
            user.phone = phone
            user.save()

            return JsonResponse(
                {
                    "success": True,
                    "message": "Profile updated successfully.",
                    "redirect_url": "/profile/",
                    "requires_otp": False,
                },
                status=200,
            )

        # Return field-specific validation errors as JSON.
        return JsonResponse(
            {
                "success": False,
                "message": "Please correct the errors below.",
                "errors": form.errors.get_json_data(),
            },
            status=400,
        )

    # Pre-fill the form with the user's current details.
    form = ProfileForm(
        initial={
            "username": user.username,
            "phone": user.phone,
            "email": user.email,
        },
        user=user,
    )

    # Render the existing edit profile page for normal browser requests.
    return render(
        request,
        "accounts/edit_profile.html",
        {
            "form": form,
            "user": user,
        },
    )
