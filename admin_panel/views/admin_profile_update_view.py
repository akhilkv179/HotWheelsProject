
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from accounts.forms import ProfileForm
from accounts.services.otp_service import generate_otp, get_otp_expiry
from accounts.services.email_service import send_otp_email


# Update admin profile information and send OTP if email is modified.
@never_cache
@require_http_methods(["GET", "POST"])
def admin_profile_update_view(request):

    # Check whether the admin is authenticated.
    if not request.user.is_authenticated:
        if "application/json" in request.headers.get("Accept", ""):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Authentication required.",
                    "redirect_url": reverse("admin_login"),
                },
                status=401,
            )

        return redirect("admin_login")

    # Only active staff members can update the admin profile.
    if not request.user.is_active or not request.user.is_staff:
        if "application/json" in request.headers.get("Accept", ""):
            return JsonResponse(
                {
                    "success": False,
                    "message": "You do not have admin access.",
                },
                status=403,
            )

        return redirect("admin_login")

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

            # If the email changes, send an OTP to the new email address.
            if email.lower() != user.email.lower():

                otp = generate_otp()
                expiry = get_otp_expiry()

                request.session["admin_email_change_new_email"] = email
                request.session["admin_email_change_otp"] = otp
                request.session["admin_email_change_otp_expiry"] = (
                    expiry.isoformat()
                )

                # Start the 30-second resend cooldown.
                request.session["admin_email_change_last_otp_resend"] = (
                    timezone.now().isoformat()
                )

                send_otp_email(email, otp)

                # Update username and phone before email verification.
                user.username = username
                user.phone = phone
                user.save()

                return JsonResponse(
                    {
                        "success": True,
                        "message": (
                            "OTP has been sent to your new email address."
                        ),
                        "redirect_url": reverse(
                            "admin_verify_email_change_otp"
                        ),
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
                    "message": "Admin profile updated successfully.",
                    "redirect_url": reverse("admin_profile"),
                    "requires_otp": False,
                },
                status=200,
            )

        # Return field-specific validation errors.
        return JsonResponse(
            {
                "success": False,
                "message": "Please correct the errors below.",
                "errors": form.errors.get_json_data(),
            },
            status=400,
        )

    # Pre-fill the form with the current admin details.
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
        "admin_panel/admin_edit_profile.html",
        {
            "form": form,
            "user": user,
        },
    )
