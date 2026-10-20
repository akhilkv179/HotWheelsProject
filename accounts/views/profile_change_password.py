from datetime import datetime

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache

from ..forms import SetNewPasswordForm
from ..services.otp_service import generate_otp, get_otp_expiry
from ..services.email_service import send_otp_email


# Check whether the frontend expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Send an OTP to the logged-in user's registered email.
@never_cache
@login_required
def change_password(request):

    # Allow only GET and POST requests.
    if request.method not in ["GET", "POST"]:
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "Only GET and POST requests are allowed.",
            }, status=405)

        return HttpResponseNotAllowed(["GET", "POST"])

    user = request.user

    if request.method == "POST":

        # Generate an OTP and its expiry time.
        otp = generate_otp()
        expiry = get_otp_expiry()

        # Store the OTP details temporarily in the user's session.
        request.session["password_change_otp"] = otp
        request.session["password_change_otp_expiry"] = expiry.isoformat()

        # Send the OTP to the user's registered email.
        send_otp_email(user.email, otp)

        # Return JSON for frontend requests.
        if wants_json(request):
            return JsonResponse({
                "success": True,
                "message": "OTP has been sent to your registered email.",
                "redirect_url": reverse("verify_password_change_otp"),
            }, status=200)

        messages.success(
            request,
            "OTP has been sent to your registered email.",
        )
        return redirect("verify_password_change_otp")

    # Display the change-password page.
    return render(request, "accounts/change_password.html")


# Verify the OTP submitted for changing the account password.
@never_cache
@login_required
def verify_password_change_otp(request):

    # Allow only GET and POST requests.
    if request.method not in ["GET", "POST"]:
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "Only GET and POST requests are allowed.",
            }, status=405)

        return HttpResponseNotAllowed(["GET", "POST"])

    stored_otp = request.session.get("password_change_otp")
    expiry_string = request.session.get("password_change_otp_expiry")

    # Check whether the OTP session exists.
    if not stored_otp or not expiry_string:
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "OTP session has expired. Please request a new OTP.",
                "redirect_url": reverse("change_password"),
            }, status=410)

        messages.error(request, "OTP session has expired.")
        return redirect("change_password")

    # Convert the stored expiry string into a datetime object.
    try:
        expiry = datetime.fromisoformat(expiry_string)
    except (ValueError, TypeError):
        expiry = None

    # Reject an invalid or expired OTP expiry time.
    if expiry is None or timezone.now() > expiry:
        request.session.pop("password_change_otp", None)
        request.session.pop("password_change_otp_expiry", None)
        request.session.pop("password_change_verified", None)

        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "OTP has expired. Please request a new OTP.",
                "redirect_url": reverse("change_password"),
            }, status=410)

        messages.error(request, "OTP has expired.")
        return redirect("change_password")

    if request.method == "POST":
        entered_otp = request.POST.get("otp", "").strip()

        # Check whether the user entered an OTP.
        if not entered_otp:
            if wants_json(request):
                return JsonResponse({
                    "success": False,
                    "message": "OTP is required.",
                }, status=400)

            messages.error(request, "OTP is required.")
            return render(
                request,
                "accounts/verify_password_change_otp.html",
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
                "accounts/verify_password_change_otp.html",
                status=400,
            )

        # Mark the OTP as verified.
        request.session["password_change_verified"] = True

        # Remove the OTP itself after successful verification.
        request.session.pop("password_change_otp", None)
        request.session.pop("password_change_otp_expiry", None)

        if wants_json(request):
            return JsonResponse({
                "success": True,
                "message": "OTP verified successfully.",
                "redirect_url": reverse("set_new_password"),
            }, status=200)

        return redirect("set_new_password")

    # Display the OTP verification page.
    return render(
        request,
        "accounts/verify_password_change_otp.html",
    )


# Save the new password after successful OTP verification.
@never_cache
@login_required
def set_new_password(request):

    # Ensure the user has verified the OTP first.
    if not request.session.get("password_change_verified"):
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "Please verify the OTP first.",
                "redirect_url": reverse("change_password"),
            }, status=403)

        messages.error(request, "Please verify the OTP first.")
        return redirect("change_password")

    # Allow only GET and POST requests.
    if request.method not in ["GET", "POST"]:
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "Only GET and POST requests are allowed.",
            }, status=405)

        return HttpResponseNotAllowed(["GET", "POST"])

    user = request.user

    if request.method == "POST":
        form = SetNewPasswordForm(
            request.POST,
            user=user,
        )

        # Validate the new password before saving it.
        if form.is_valid():
            new_password = form.cleaned_data["new_password"]

            # Hash and save the new password securely.
            user.set_password(new_password)
            user.save()

            # Keep the user logged in after the password change.
            update_session_auth_hash(request, user)

            # Clear the verification flag after a successful change.
            request.session.pop("password_change_verified", None)

            if wants_json(request):
                return JsonResponse({
                    "success": True,
                    "message": "Password changed successfully.",
                    "redirect_url": reverse("profile"),
                }, status=200)

            messages.success(
                request,
                "Password changed successfully.",
            )
            return redirect("profile")

        # Return password validation errors as JSON when requested.
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "Please correct the password form errors.",
                "errors": form.errors.get_json_data(),
            }, status=400)

        # Display validation errors using Django messages.
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)

    else:
        form = SetNewPasswordForm(user=user)

    # Display the new-password form.
    return render(
        request,
        "accounts/set_new_password.html",
        {"form": form},
    )