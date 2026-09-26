from django.contrib import messages
from django.shortcuts import render, redirect
from django.utils import timezone


def admin_verify_forgot_password_otp(request):

    email = request.session.get("admin_forgot_password_email")
    stored_otp = request.session.get("admin_forgot_password_otp")
    otp_expiry = request.session.get("admin_forgot_password_otp_expiry")

    if not email or not stored_otp or not otp_expiry:
        messages.error(
            request,
            "Your OTP session has expired. Please request a new OTP."
        )
        return redirect("admin_forgot_password")

    if request.method == "POST":

        entered_otp = request.POST.get("otp", "").strip()

        if not entered_otp:
            messages.error(request, "Please enter the OTP.")
            return render(
                request,
                "admin_panel/admin_verify_forgot_password_otp.html"
            )

        if timezone.now() > timezone.datetime.fromisoformat(
            otp_expiry
        ).replace(tzinfo=timezone.get_current_timezone()):

            messages.error(
                request,
                "OTP has expired. Please request a new OTP."
            )

            return redirect("admin_forgot_password")

        if entered_otp != stored_otp:
            messages.error(
                request,
                "Invalid OTP. Please try again."
            )

            return render(
                request,
                "admin_panel/admin_verify_forgot_password_otp.html"
            )

        request.session["admin_forgot_password_otp_verified"] = True

        return redirect("admin_set_new_password")

    return render(
        request,
        "admin_panel/admin_verify_forgot_password_otp.html"
    )