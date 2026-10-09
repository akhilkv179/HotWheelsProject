
import re
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.views.decorators.cache import never_cache
from ..models import User
from ..services.otp_service import generate_otp, get_otp_expiry
from ..services.email_service import send_otp_email


@never_cache
@login_required
def edit_profile(request):


    user = request.user

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        phone = request.POST.get("phone", "").strip()
        email = request.POST.get("email", "").strip()

        if not username:
            messages.error(request, "Username is required.")
            return render(request, "accounts/edit_profile.html")

        if not re.fullmatch(r"[A-Za-z0-9]+", username):
            messages.error(request, "Username must contain only letters and numbers.")
            return render(request, "accounts/edit_profile.html")

        if not phone:
            messages.error(request, "Phone number is required.")
            return render(request, "accounts/edit_profile.html")

        if not re.fullmatch(r"[0-9]{10}", phone):
            messages.error(request, "Phone number must contain exactly 10 digits.")
            return render(request, "accounts/edit_profile.html")

        username_exists = User.objects.filter(
            username__iexact=username
        ).exclude(id=user.id).exists()

        if username_exists:
            messages.error(request, "This username is already taken.")
            return render(request, "accounts/edit_profile.html")

        if not email:
            messages.error(request, "Email is required.")
            return render(request, "accounts/edit_profile.html")

        if email.lower() != user.email.lower():
            email_exists = User.objects.filter(
                email__iexact=email
            ).exclude(id=user.id).exists()

            if email_exists:
                messages.error(request, "This email has already been taken.")
                return render(request, "accounts/edit_profile.html")

            otp = generate_otp()
            expiry = get_otp_expiry()

            request.session["email_change_new_email"] = email
            request.session["email_change_otp"] = otp
            request.session["email_change_otp_expiry"] = expiry.isoformat()

            send_otp_email(email, otp)

            user.username = username
            user.phone = phone
            user.save()

            messages.success(
                request,
                "OTP has been sent to your new email address."
            )
            return redirect("verify_email_change_otp")

        user.username = username
        user.phone = phone
        user.save()

        messages.success(request, "Profile updated successfully.")
        return redirect("profile")

    return render(request, "accounts/edit_profile.html")