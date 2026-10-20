from datetime import datetime

from django.contrib import messages
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache

from ..forms import ResetPasswordForm
from ..models import User


# Check whether the frontend expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Verify the OTP submitted by the user for resetting their password.
@never_cache
def verify_reset_otp(request):

    # Allow OTP verification only through GET and POST requests.
    if request.method not in ["GET", "POST"]:
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "Only GET and POST requests are allowed.",
            }, status=405)

        return HttpResponseNotAllowed(["GET", "POST"])

    if request.method == "POST":
        entered_otp = request.POST.get("otp", "").strip()

        stored_otp = request.session.get("reset_otp")
        stored_expiry = request.session.get("reset_otp_expiry")
        reset_email = request.session.get("reset_email")

        # Check whether the password-reset session data exists.
        if not stored_otp or not stored_expiry or not reset_email:
            if wants_json(request):
                return JsonResponse({
                    "success": False,
                    "message": "OTP session has expired. Please request a new OTP.",
                    "redirect_url": reverse("forgot_password"),
                }, status=410)

            messages.error(
                request,
                "OTP session has expired. Please request a new OTP.",
            )
            return redirect("forgot_password")

        # Convert the saved expiry string into a datetime object.
        try:
            expiry_time = datetime.fromisoformat(stored_expiry)
        except (ValueError, TypeError):
            expiry_time = None

        # Reject an invalid or expired OTP expiry time.
        if expiry_time is None or timezone.now() > expiry_time:
            request.session.pop("reset_otp_verified", None)

            if wants_json(request):
                return JsonResponse({
                    "success": False,
                    "message": "OTP has expired. Please request a new OTP.",
                    "redirect_url": reverse("forgot_password"),
                }, status=410)

            messages.error(
                request,
                "OTP has expired. Please request a new OTP.",
            )
            return redirect("forgot_password")

        # Reject an empty OTP.
        if not entered_otp:
            if wants_json(request):
                return JsonResponse({
                    "success": False,
                    "message": "Please enter the OTP.",
                }, status=400)

            messages.error(request, "Please enter the OTP.")
            return render(
                request,
                "accounts/verify_reset_otp.html",
                status=400,
            )

        # Check whether the entered OTP matches the stored OTP.
        if entered_otp != stored_otp:
            if wants_json(request):
                return JsonResponse({
                    "success": False,
                    "message": "Invalid OTP.",
                }, status=400)

            messages.error(request, "Invalid OTP.")
            return render(
                request,
                "accounts/verify_reset_otp.html",
                status=400,
            )

        # Mark the OTP as verified for the password-reset process.
        request.session["reset_otp_verified"] = True

        if wants_json(request):
            return JsonResponse({
                "success": True,
                "message": "OTP verified successfully.",
                "redirect_url": reverse("reset_password"),
            }, status=200)

        return redirect("reset_password")

    # Display the OTP verification page.
    return render(request, "accounts/verify_reset_otp.html")


# Allow the user to set a new password after verifying their reset OTP.
@never_cache
def reset_password(request):

    # Ensure the OTP was verified and reset session data still exists.
    if (
        not request.session.get("reset_otp_verified")
        or not request.session.get("reset_email")
    ):
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "Please verify the OTP first.",
                "redirect_url": reverse("forgot_password"),
            }, status=403)

        messages.error(request, "Please verify the OTP first.")
        return redirect("forgot_password")

    # Allow password resetting only through GET and POST requests.
    if request.method not in ["GET", "POST"]:
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "Only GET and POST requests are allowed.",
            }, status=405)

        return HttpResponseNotAllowed(["GET", "POST"])

    if request.method == "POST":
        form = ResetPasswordForm(request.POST)

        # Validate the new password before saving it.
        if form.is_valid():
            new_password = form.cleaned_data["new_password"]
            reset_email = request.session.get("reset_email")

            # Find the account associated with the password-reset request.
            user = User.objects.filter(
                email__iexact=reset_email,
            ).first()

            if user is None:
                if wants_json(request):
                    return JsonResponse({
                        "success": False,
                        "message": (
                            "Account not found. Please request a new "
                            "password reset."
                        ),
                        "redirect_url": reverse("forgot_password"),
                    }, status=404)

                messages.error(
                    request,
                    "Account not found. Please request a new password reset.",
                )
                return redirect("forgot_password")

            # Save the new password using Django's secure password hashing.
            user.set_password(new_password)
            user.save()

            # Clear password-reset session data after a successful reset.
            request.session.pop("reset_email", None)
            request.session.pop("reset_otp", None)
            request.session.pop("reset_otp_expiry", None)
            request.session.pop("reset_otp_verified", None)

            if wants_json(request):
                return JsonResponse({
                    "success": True,
                    "message": "Password reset successfully. Please login.",
                    "redirect_url": reverse("login"),
                }, status=200)

            messages.success(
                request,
                "Password reset successfully. Please login.",
            )
            return redirect("login")

        # Return validation errors to a frontend expecting JSON.
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "Please correct the password form errors.",
                "errors": form.errors.get_json_data(),
            }, status=400)

        # Display form validation errors through Django messages.
        errors = []
        for field_errors in form.errors.values():
            errors.extend(field_errors)

        for error in dict.fromkeys(errors):
            messages.error(request, error)

    else:
        form = ResetPasswordForm()

    # Display the password-reset page with the form.
    return render(
        request,
        "accounts/reset_password.html",
        {"form": form},
    )