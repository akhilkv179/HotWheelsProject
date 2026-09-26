from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone
from datetime import datetime

from ..models import User


@login_required
def verify_email_change_otp(request):

    new_email = request.session.get("email_change_new_email")
    stored_otp = request.session.get("email_change_otp")
    expiry_string = request.session.get("email_change_otp_expiry")

    if not new_email or not stored_otp or not expiry_string:
        messages.error(request, "Email verification session has expired.")
        return redirect("edit_profile")

    expiry = datetime.fromisoformat(expiry_string)

    if  request.method == "POST":

        entered_otp = request.POST.get("otp","").strip()

        if not entered_otp:
            messages.error(request,"otp is required")
            return render(request,"accounts/verify_email_change_otp.html")

        if timezone.now() > expiry:
            messages.error(request,"OTP has expired")
            return redirect("edit_profile")

        if entered_otp != stored_otp:
            messages.error(request,"Invalid OTP.")
            return render(request,"accounts/verify_email_change_otp.html")

        user = request.user

        email_exists = User.objects.filter(email__iexact = new_email).exclude(id = user.id).exists()

        if email_exists:
            messages.error(request,"This email is already registered.")

            request.session.pop("email_change_new_email",None)
            request.session.pop("email_change_otp", None)
            request.session.pop("email_change_otp_expiry", None)

            return redirect("edit_profile")

        user.email = new_email
        user.save()

        request.session.pop("email_change_new_email", None)
        request.session.pop("email_change_otp", None)
        request.session.pop("email_change_otp_expiry", None)

        messages.success(request,"Email updated succesfully.")
        return redirect("profile")

    return render(request,"accounts/verify_email_change_otp.html")




