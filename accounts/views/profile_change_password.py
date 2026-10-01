from django.contrib import messages
from django.contrib.auth import authenticate,login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.shortcuts import render,redirect
from ..services.otp_service import generate_otp, get_otp_expiry
from ..services.email_service import send_otp_email
from django.utils import timezone
from django.contrib.auth import update_session_auth_hash
from datetime import datetime
from django.views.decorators.cache import never_cache

@never_cache
@login_required
def change_password(request):

    user = request.user

    if request.method == "POST":

        otp = generate_otp()
        expiry = get_otp_expiry()

        request.session["password_change_otp"] = otp
        request.session["password_change_otp_expiry"] = expiry.isoformat()

        send_otp_email(user.email, otp)

        messages.success(request,"OTP has been sent to your registered email.")
        return redirect("verify_password_change_otp")

    return render(request, "accounts/change_password.html")

@never_cache
def verify_password_change_otp(request):

    stored_otp = request.session.get("password_change_otp")
    expiry_string = request.session.get("password_change_otp_expiry")


    if not stored_otp or not expiry_string:
        messages.error(request,"OTP session has expired.")
        return redirect("change_password")

    expiry = datetime.fromisoformat(expiry_string)

    if request.method == "POST":
        entered_otp = request.POST.get("otp","").strip()

        if not entered_otp:
            messages.error(request,"OTP is required")
            return render(request,"accounts/verify_password_change_otp.html")

        if timezone.now() > expiry:
            messages.error(request,"OTP has expired")
            return render(request,"accounts/verify_password_change_otp.html")

        if entered_otp != stored_otp:
            messages.error(request,"Invalid OTP")
            return render(request,"accounts/verify_password_change_otp.html")

        request.session["password_change_verified"] = True

        request.session.pop("password_change_otp",None)
        request.session.pop("password_change_otp_expiry",None)

        return redirect("set_new_password")
    
    return render(request,"accounts/verify_password_change_otp.html")

@never_cache
def set_new_password(request):

    if not request.session.get("password_change_verified"):
        messages.error(request,"please verify the otp")
        return redirect("change_password")

    user = request.user

    if request.method == "POST":

        new_password = request.POST.get("new_password","")
        confirm_password = request.POST.get("confirm_password","")

        if not new_password:
            messages.error(request,"New password is required")
            return render(request,"accounts/set_new_password.html")

        if new_password != confirm_password:
            messages.error(request,"password do not match")
            return render(request,"accounts/set_new_password.html")

        try:
            validate_password(new_password)
        except ValidationError as error:
            for message in error.messages:
                messages.error(request,message)

            return render(request,"accounts/set_new_password.html")

        user.set_password(new_password)
        user.save()

        update_session_auth_hash(request,user)

        request.session.pop("password_change_verified",None)

        messages.success(request,"Password changed successfully.")
        return redirect("profile")

    return render(request,"accounts/set_new_password.html")


                                            
            
            