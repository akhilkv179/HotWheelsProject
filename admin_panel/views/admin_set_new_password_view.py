from django.contrib import messages
from django.shortcuts import render, redirect

from accounts.models import User


def admin_set_new_password(request):

    email = request.session.get("admin_forgot_password_email")
    otp_verified = request.session.get(
        "admin_forgot_password_otp_verified"
    )

    if not email or not otp_verified:
        messages.error(
            request,
            "Please verify the OTP first."
        )
        return redirect("admin_forgot_password")

    if request.method == "POST":

        password = request.POST.get("password", "")
        confirm_password = request.POST.get(
            "confirm_password",
            ""
        )

        if not password or not confirm_password:
            messages.error(
                request,
                "Both password fields are required."
            )
            return render(
                request,
                "admin_panel/admin_set_new_password.html"
            )

        if password != confirm_password:
            messages.error(
                request,
                "Passwords do not match."
            )
            return render(
                request,
                "admin_panel/admin_set_new_password.html"
            )

        user = User.objects.filter(
            email__iexact=email,
            is_staff=True
        ).first()

        if not user:
            messages.error(
                request,
                "Admin account not found."
            )
            return redirect("admin_forgot_password")

        user.set_password(password)
        user.save()

        # Clear forgot-password session data
        request.session.pop(
            "admin_forgot_password_email",
            None
        )
        request.session.pop(
            "admin_forgot_password_otp",
            None
        )
        request.session.pop(
            "admin_forgot_password_otp_expiry",
            None
        )
        request.session.pop(
            "admin_forgot_password_otp_verified",
            None
        )

        messages.success(
            request,
            "Password changed successfully. Please login."
        )

        return redirect("admin_login")

    return render(
        request,
        "admin_panel/admin_set_new_password.html"
    )