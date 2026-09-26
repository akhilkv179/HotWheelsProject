from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from ..models import User
from ..services.otp_service import generate_otp, get_otp_expiry
from ..services.email_service import send_otp_email







def edit_profile(request):

    user = request.user


    if request.method == "POST":
        username = request.POST.get("username","").strip()
        phone = request.POST.get("phone","").strip()
        email = request.POST.get("email","").strip()
       


        if not username:
            messages.error(request,"username is required")
            return render(request,"accounts/edit_profile.html")

        if not phone:
            messages.error("phone number is required")
            return render(request,"accounts/edit_profile.html")
        
        


        username_exists = User.objects.filter(username__iexact = username).exclude(id = user.id).exists()
        if username_exists:
            messages.error(request,"This username already taken")
            return render(request,"accounts/edit_profile.html")


        if not email:
            messages.error(request, "Email is required.")
            return render(request, "accounts/edit_profile.html")

        if email.lower() != user.email.lower():

            email_exists = User.objects.filter(email__iexact = email).exclude(id = user.id).exists()

            if email_exists:
                messages.error(request,"This email has alreay taken")
                return render(request,"accounts/edit_profile.html")

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
        messages.success(request,"profile updated successfully")

        return redirect("profile")

    return render(request,"accounts/edit_profile.html")


        
