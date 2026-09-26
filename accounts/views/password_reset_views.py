from django.contrib import messages
from django.shortcuts import render, redirect
from datetime import datetime
from django.utils import timezone
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from ..models import User


def verify_reset_otp(request):
    if request.method == "POST":
        entered_otp = request.POST.get("otp", "").strip()

        stored_otp = request.session.get("reset_otp")

        if not stored_otp:
            messages.error(request, "OTP session has expired. Please request a new OTP.")
            return redirect("forgot_password")

        stored_expiry = request.session.get("reset_otp_expiry")

        expiry_time = datetime.fromisoformat(stored_expiry)

        if timezone.now() > expiry_time:
            messages.error(request,"OTP has expired. Please request a new OTP.")
            return redirect("forgot_password")

        if entered_otp != stored_otp:
            messages.error(request,"Invalid OTP.")
            return render(request,"accounts/verify_reset_otp.html")

        request.session["reset_otp_verified"] = True
        return redirect("reset_password")

    return render( request,"accounts/verify_reset_otp.html")


def reset_password(request):
    if not request.session.get("reset_otp_verified"):
        messages.error(request,"Please verify the OTP first.")
        return redirect("forgot_password")

    if request.method == "POST":
        new_password = request.POST.get("new_password", "")
        confirm_password = request.POST.get("confirm_password", "")

        if not new_password or not confirm_password:
            messages.error(request,"Both password fields are required.")
            return render(request,"accounts/reset_password.html")

        if new_password != confirm_password:
            messages.error(request,"Passwords do not match." )
            return render(request,"accounts/reset_password.html")


        try:
            validate_password(new_password)
        except ValidationError as error:
            messages.error(request, error.messages[0])
            return render(request,"accounts/reset_password.html")

        reset_email = request.session.get("reset_email")
        user = User.objects.filter(email=reset_email).first()

        user.set_password(new_password)
        user.save()

        request.session.pop("reset_email", None)
        request.session.pop("reset_otp", None)
        request.session.pop("reset_otp_expiry", None)
        request.session.pop("reset_otp_verified", None)

        messages.success(request,"Password reset successfully. Please login.")
        return redirect("login")

    return render(request,"accounts/reset_password.html")

