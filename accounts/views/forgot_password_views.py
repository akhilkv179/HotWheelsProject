from django.contrib import messages
from django.shortcuts import render, redirect
from ..models import User
from ..services.otp_service import generate_otp, get_otp_expiry
from ..services.email_service import send_otp_email


def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip()

        if not email:
            messages.error(request, "Email is required.")
            return render(request, "accounts/forgot_password.html")

        user = User.objects.filter(email__iexact=email).first()

        if user is None:
            messages.error( request,"No account found with this email.")
            return render(request,"accounts/forgot_password.html")


        

        request.session["reset_email"] = user.email
        otp = generate_otp()
        otp_expiry = get_otp_expiry()

        request.session["reset_otp"] = otp
        request.session["reset_otp_expiry"] = otp_expiry.isoformat()

        send_otp_email(user.email, otp)

        messages.success(request, "OTP has been sent to your email.")
        return redirect("verify_reset_otp")

    return render(request,"accounts/forgot_password.html")