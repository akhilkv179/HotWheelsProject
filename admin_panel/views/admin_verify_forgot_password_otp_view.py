
from datetime import datetime

from django.contrib import messages
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils import timezone


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Verify the OTP submitted by an administrator during password recovery.
def admin_verify_forgot_password_otp(request):

    email = request.session.get("admin_reset_email")
    stored_otp = request.session.get("admin_reset_otp")
    otp_expiry = request.session.get("admin_reset_otp_expiry")

    # Check whether the OTP session exists.
    if not email or not stored_otp or not otp_expiry:

        error_message = (
            "Your OTP session has expired. Please request a new OTP."
        )

        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": error_message,
                    "redirect_url": reverse("admin_forgot_password"),
                },
                status=410,
            )

        messages.error(request, error_message)
        return redirect("admin_forgot_password")

    # Allow only GET and POST requests.
    if request.method not in ["GET", "POST"]:

        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Method not allowed.",
                },
                status=405,
            )

        return HttpResponseNotAllowed(["GET", "POST"])

    if request.method == "POST":

        entered_otp = request.POST.get("otp", "").strip()

        # Check whether the admin entered an OTP.
        if not entered_otp:

            error_message = "Please enter the OTP."

            if wants_json(request):
                return JsonResponse(
                    {
                        "success": False,
                        "message": error_message,
                    },
                    status=400,
                )

            messages.error(request, error_message)
            return render(
                request,
                "admin_panel/admin_verify_forgot_password_otp.html",
            )

        # Convert the stored expiry string into a datetime.
        expiry_time = datetime.fromisoformat(otp_expiry)

        if timezone.is_naive(expiry_time):
            expiry_time = timezone.make_aware(
                expiry_time,
                timezone.get_current_timezone(),
            )

        # Check whether the OTP has expired.
        if timezone.now() > expiry_time:

            error_message = "OTP has expired. Please request a new OTP."

            if wants_json(request):
                return JsonResponse(
                    {
                        "success": False,
                        "message": error_message,
                        "redirect_url": reverse("admin_forgot_password"),
                    },
                    status=410,
                )

            messages.error(request, error_message)
            return redirect("admin_forgot_password")

        # Compare the entered OTP with the stored OTP.
        if entered_otp != stored_otp:

            error_message = "Invalid OTP. Please try again."

            if wants_json(request):
                return JsonResponse(
                    {
                        "success": False,
                        "message": error_message,
                    },
                    status=400,
                )

            messages.error(request, error_message)
            return render(
                request,
                "admin_panel/admin_verify_forgot_password_otp.html",
            )

        # Mark the admin OTP as verified.
        request.session["admin_reset_otp_verified"] = True

        if wants_json(request):
            return JsonResponse(
                {
                    "success": True,
                    "message": "OTP verified successfully.",
                    "redirect_url": reverse("admin_set_new_password"),
                },
                status=200,
            )

        return redirect("admin_set_new_password")

    if wants_json(request):
        return JsonResponse(
            {
                "success": True,
                "message": "Enter the OTP sent to your email.",
            },
            status=200,
        )

    return render(
        request,
        "admin_panel/admin_verify_forgot_password_otp.html",
    )
