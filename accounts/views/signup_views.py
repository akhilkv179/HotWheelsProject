from django.contrib import messages
from ..models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from ..services.otp_service import generate_otp, get_otp_expiry
from django.contrib.auth.hashers import make_password
from ..services.email_service import send_otp_email
import re


def signup(request):
    if request.method == "POST":
        username = request.POST.get("username","").strip()
        email = request.POST.get("email","").strip()
        phone = request.POST.get("phone","").strip()
        password = request.POST.get("password","")
        confirm_password = request.POST.get("confirm_password","")


        # it is regax pattern for checking the username,email and password
        # the re.fullmatch() check the entire username is match with the pattern

        name_pattern = r"^[A-Za-z ]+$"
        email_pattern = r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
        phone_pattern = r"^[6-9]\d{9}$"

        if not username:
            messages.error(request, "Username is required.")
            return render(request, "accounts/signup.html")

        if not email:
            messages.error(request, "Email is required.")
            return render(request, "accounts/signup.html")

        if not phone:
            messages.error(request, "Phone number is required.")
            return render(request, "accounts/signup.html")

        if not password:
            messages.error(request, "Password is required.")
            return render(request, "accounts/signup.html")

        if not confirm_password:
            messages.error(request, "Please confirm your password.")
            return render(request, "accounts/signup.html")

        # this checks the username is following the name_pattern and same  for email and password

        if not re.fullmatch(name_pattern, username):
            messages.error(
                request,
                "Name can contain only letters and spaces."
            )
            return render(request, "accounts/signup.html")
        
        if not re.fullmatch(email_pattern, email):
            messages.error(
                request,
                "Please enter a valid email address."
            )
            return render(request, "accounts/signup.html")

        if not re.fullmatch(phone_pattern, phone):
            messages.error(
                request,
                "Please enter a valid 10-digit phone number."
            )
            return render(request, "accounts/signup.html")



        

        if password != confirm_password:
            messages.error(request,"passwords do not match.")
            return render(request,"accounts/signup.html")


        if User.objects.filter(username = username).exists():
            messages.error(request,"username already exists.")
            return render(request,"accounts/signup.html")
        
        if User.objects.filter(email__iexact=email).exists():
            messages.error(request,"Email already exists")
            return render(request,"accounts/signup.html")

        # validate_password(password) checks the password with password validator

        try:
            validate_password(password)
        except ValidationError as error:
            for message in error.messages:
                messages.error(request, message)

            return render(request,"accounts/signup.html")

        password_hash = make_password(password)

        request.session["signup_data"] = {
            "username": username,
            "email": email,
            "phone": phone,
            "password_hash": password_hash,
        }

        otp = generate_otp()        
        otp_expiry = get_otp_expiry()



        # Why do we store the OTP in the session?
        # Because when the user moves from the signup page to the OTP page, Django needs to remember which OTP it generated.
        request.session["signup_otp"] = otp
        # isoformat() is used to convert the Python datetime into a string that can be stored in the session.
        request.session["signup_otp_expiry"] = otp_expiry.isoformat()


        send_otp_email(email, otp)


        return redirect("verify_otp")
    
        
    return render(request, "accounts/signup.html")
    