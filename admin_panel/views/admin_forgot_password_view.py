from django.contrib import messages
from django.shortcuts import render, redirect

from accounts.models import User
from accounts.services.otp_service import generate_otp, get_otp_expiry
from accounts.services.email_service import send_otp_email


def admin_forgot_password(request):

    if request.method == "POST":

        email = request.POST.get("email", "").strip()

        if not email:
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

        messages.success(
            request,
            "OTP has been sent to your email address."
        )

        return redirect("admin_verify_forgot_password_otp")

    return render(
        request,
        "admin_panel/admin_forgot_password.html"
    )