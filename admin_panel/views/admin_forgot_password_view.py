from django.contrib import messages
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render, redirect
from django.urls import reverse

from accounts.models import User
from accounts.services.otp_service import generate_otp, get_otp_expiry
from accounts.services.email_service import send_otp_email


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Send a password reset OTP to an administrator's email.
def admin_forgot_password(request):

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

    if request.method == "GET":
        if wants_json(request):
            return JsonResponse(
                {
                    "success": True,
                    "message": "Submit the administrator email to request a password reset OTP."
                },
                status=200
            )

        return render(
            request,
            "admin_panel/admin_forgot_password.html"
        )

    email = request.POST.get("email", "").strip()

    if not email:
        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Email is required."
                },
                status=400
            )

        messages.error(request, "Email is required.")
        return render(
            request,
            "admin_panel/admin_forgot_password.html"
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
                    "message": "No admin account found with this email."
                },
                status=404
            )

        messages.error(
            request,
            "No admin account found with this email."
        )
        return render(
            request,
            "admin_panel/admin_forgot_password.html"
        )

    otp = generate_otp()
    expiry = get_otp_expiry()

    request.session["admin_forgot_password_email"] = email
    request.session["admin_forgot_password_otp"] = otp
    request.session["admin_forgot_password_otp_expiry"] = expiry.isoformat()

    send_otp_email(email, otp)

    if wants_json(request):
        return JsonResponse(
            {
                "success": True,
                "message": "OTP has been sent to your email address.",
                "redirect_url": reverse("admin_verify_forgot_password_otp")
            },
            status=202
        )

    messages.success(
        request,
        "OTP has been sent to your email address."
    )

    return redirect("admin_verify_forgot_password_otp")