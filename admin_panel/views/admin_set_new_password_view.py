from django.contrib import messages
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render, redirect
from django.urls import reverse

from accounts.models import User


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Validate and set a new password for the administrator after OTP verification.
def admin_set_new_password(request):

    email = request.session.get("admin_forgot_password_email")
    otp_verified = request.session.get(
        "admin_forgot_password_otp_verified"
    )

    if not email or not otp_verified:
        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Please verify the OTP first.",
                    "redirect_url": reverse("admin_forgot_password")
                },
                status=403
            )

        messages.error(
            request,
            "Please verify the OTP first."
        )
        return redirect("admin_forgot_password")

    if request.method not in ["GET", "POST"]:
        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Method not allowed."
                },
                status=405
            )

        return HttpResponseNotAllowed(["GET", "POST"])

    if request.method == "POST":

        password = request.POST.get("password", "")
        confirm_password = request.POST.get(
            "confirm_password",
            ""
        )

        if not password or not confirm_password:
            error_message = "Both password fields are required."

            if wants_json(request):
                return JsonResponse(
                    {
                        "success": False,
                        "message": error_message
                    },
                    status=400
                )

            messages.error(request, error_message)
            return render(
                request,
                "admin_panel/admin_set_new_password.html"
            )

        if password != confirm_password:
            error_message = "Passwords do not match."

            if wants_json(request):
                return JsonResponse(
                    {
                        "success": False,
                        "message": error_message
                    },
                    status=400
                )

            messages.error(request, error_message)
            return render(
                request,
                "admin_panel/admin_set_new_password.html"
            )

        user = User.objects.filter(
            email__iexact=email,
            is_staff=True
        ).first()

        if not user:
            if wants_json(request):
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Admin account not found.",
                        "redirect_url": reverse("admin_forgot_password")
                    },
                    status=404
                )

            messages.error(
                request,
                "Admin account not found."
            )
            return redirect("admin_forgot_password")

        user.set_password(password)
        user.save()

        # Clear forgot-password session data.
        request.session.pop("admin_forgot_password_email", None)
        request.session.pop("admin_forgot_password_otp", None)
        request.session.pop("admin_forgot_password_otp_expiry", None)
        request.session.pop("admin_forgot_password_otp_verified", None)

        if wants_json(request):
            return JsonResponse(
                {
                    "success": True,
                    "message": "Password changed successfully. Please login.",
                    "redirect_url": reverse("admin_login")
                },
                status=200
            )

        messages.success(
            request,
            "Password changed successfully. Please login."
        )

        return redirect("admin_login")

    if wants_json(request):
        return JsonResponse(
            {
                "success": True,
                "message": "Enter your new password."
            },
            status=200
        )

    return render(
        request,
        "admin_panel/admin_set_new_password.html"
    )