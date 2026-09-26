from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from .services.otp_service import generate_otp


def signup(request):
    if request.method == "POST":
        username = request.POST.get("username","").strip()
        email = request.POST.get("email","").strip()
        phone = request.POST.get("phone","").strip()
        password = request.POST.get("password","")
        confirm_password = request.POST.get("confirm_password","")

        User = get_user_model()

        if password != confirm_password:
            messages.error(request,"passwords do not match.")
            return render(request,"accounts/signup.html")

        if User.objects.filter(username = username).exists():
            messages.error(request,"username already exists.")
            return render(request,"accounts/signup.html")
        
        if User.objects.filter(email__iexact=email).exists():
            messages.error(request,"Email already exists")
            return render(request,"accounts/signup.html")

        try:
            validate_password(password)
        except ValidationError as error:
            for message in error.messages:
                messages.error(request, message)

            return render(request,"accounts/signup.html")

        otp = generate_otp()

        request.session["signup_otp"] = otp
        request.session["signup_email"] = email

        print("OTP:", otp)

        return redirect("verify_otp")
    
        
    return render(request, "accounts/signup.html")
    