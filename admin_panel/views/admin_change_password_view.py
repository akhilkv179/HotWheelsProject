
from datetime import datetime

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache

from accounts.forms import SetNewPasswordForm
from accounts.services.otp_service import generate_otp, get_otp_expiry
from accounts.services.email_service import send_otp_email


# Check whether the frontend expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Send an OTP to the logged-in admin's registered email.
@never_cache
def admin_change_password_view(request):

    if not request.user.is_authenticated:
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "Authentication required.",
                "redirect_url": reverse("admin_login"),
            }, status=401)

        return redirect("admin_login")

    if not request.user.is_active or not request.user.is_staff:
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "You do not have admin access.",
            }, status=403)

        return redirect("admin_login")

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

        # Store OTP details in the admin session.
        request.session["admin_password_change_otp"] = otp
        request.session["admin_password_change_otp_expiry"] = (
            expiry.isoformat()
        )

        # Start the 30-second resend cooldown.
        request.session["admin_password_change_last_otp_resend"] = (
            timezone.now().isoformat()
        )

        # Clear previous verification status.
        request.session.pop("admin_password_change_verified", None)

        # Send OTP to the admin's registered email.
        send_otp_email(user.email, otp)

        if wants_json(request):
            return JsonResponse({
                "success": True,
                "message": "OTP has been sent to your registered email.",
                "redirect_url": reverse(
                    "admin_verify_password_change_otp"
                ),
            }, status=200)

        messages.success(
            request,
            "OTP has been sent to your registered email.",
        )

        return redirect("admin_verify_password_change_otp")

    return render(
        request,
        "admin_panel/admin_change_password.html",
    )


# Verify the OTP submitted for changing the admin password.
@never_cache
def admin_verify_password_change_otp_view(request):

    if not request.user.is_authenticated:
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "Authentication required.",
                "redirect_url": reverse("admin_login"),
            }, status=401)

        return redirect("admin_login")

    if not request.user.is_active or not request.user.is_staff:
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "You do not have admin access.",
            }, status=403)

        return redirect("admin_login")

    if request.method not in ["GET", "POST"]:
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "Only GET and POST requests are allowed.",
            }, status=405)

        return HttpResponseNotAllowed(["GET", "POST"])

    stored_otp = request.session.get("admin_password_change_otp")
    expiry_string = request.session.get(
        "admin_password_change_otp_expiry"
    )

    if not stored_otp or not expiry_string:
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "OTP session has expired. Please request a new OTP.",
                "redirect_url": reverse("admin_change_password"),
            }, status=410)

        messages.error(request, "OTP session has expired.")
        return redirect("admin_change_password")

    try:
        expiry = datetime.fromisoformat(expiry_string)
    except (ValueError, TypeError):
        expiry = None

    if expiry is None or timezone.now() > expiry:

        request.session.pop("admin_password_change_otp", None)
        request.session.pop("admin_password_change_otp_expiry", None)
        request.session.pop("admin_password_change_verified", None)
        request.session.pop(
            "admin_password_change_last_otp_resend", None
        )

        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "OTP has expired. Please request a new OTP.",
                "redirect_url": reverse("admin_change_password"),
            }, status=410)

        messages.error(request, "OTP has expired.")
        return redirect("admin_change_password")

    if request.method == "POST":

        entered_otp = request.POST.get("otp", "").strip()

        if not entered_otp:
            if wants_json(request):
                return JsonResponse({
                    "success": False,
                    "message": "OTP is required.",
                }, status=400)

            messages.error(request, "OTP is required.")

            return render(
                request,
                "admin_panel/admin_verify_password_change_otp.html",
                status=400,
            )

        if entered_otp != stored_otp:
            if wants_json(request):
                return JsonResponse({
                    "success": False,
                    "message": "Invalid OTP.",
                }, status=400)

            messages.error(request, "Invalid OTP.")

            return render(
                request,
                "admin_panel/admin_verify_password_change_otp.html",
                status=400,
            )

        # Mark the OTP as verified.
        request.session["admin_password_change_verified"] = True

        request.session.pop("admin_password_change_otp", None)
        request.session.pop("admin_password_change_otp_expiry", None)
        request.session.pop(
            "admin_password_change_last_otp_resend", None
        )

        if wants_json(request):
            return JsonResponse({
                "success": True,
                "message": "OTP verified successfully.",
                "redirect_url": reverse(
                    "admin_set_new_password_after_change"
                ),
            }, status=200)

        return redirect("admin_set_new_password_after_change")

    return render(
        request,
        "admin_panel/admin_verify_password_change_otp.html",
    )


# Save the new password after successful OTP verification.
@never_cache
def admin_set_new_password_after_change_view(request):

    if not request.user.is_authenticated:
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "Authentication required.",
                "redirect_url": reverse("admin_login"),
            }, status=401)

        return redirect("admin_login")

    if not request.user.is_active or not request.user.is_staff:
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "You do not have admin access.",
            }, status=403)

        return redirect("admin_login")

    if not request.session.get("admin_password_change_verified"):
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "Please verify the OTP first.",
                "redirect_url": reverse("admin_change_password"),
            }, status=403)

        messages.error(request, "Please verify the OTP first.")
        return redirect("admin_change_password")

    if request.method not in ["GET", "POST"]:
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "Only GET and POST requests are allowed.",
            }, status=405)

        return HttpResponseNotAllowed(["GET", "POST"])

    user = request.user

    if request.method == "POST":

        form = SetNewPasswordForm(request.POST, user=user)

        if form.is_valid():

            new_password = form.cleaned_data["new_password"]

            user.set_password(new_password)
            user.save()

            # Keep the admin logged in after changing the password.
            update_session_auth_hash(request, user)

            # Clear password-change session data.
            request.session.pop(
                "admin_password_change_verified", None
            )
            request.session.pop(
                "admin_password_change_otp", None
            )
            request.session.pop(
                "admin_password_change_otp_expiry", None
            )
            request.session.pop(
                "admin_password_change_last_otp_resend", None
            )

            if wants_json(request):
                return JsonResponse({
                    "success": True,
                    "message": "Password changed successfully.",
                    "redirect_url": reverse("admin_profile"),
                }, status=200)

            messages.success(
                request,
                "Password changed successfully.",
            )

            return redirect("admin_profile")

        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "Please correct the password form errors.",
                "errors": form.errors.get_json_data(),
            }, status=400)

        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)

    else:
        form = SetNewPasswordForm(user=user)

    return render(
        request,
        "admin_panel/admin_set_new_password_after_change.html",
        {"form": form},
    )
