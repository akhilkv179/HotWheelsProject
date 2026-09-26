from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.db.models import Q
from ..models import User





def login_view(request):
    if request.method == "POST":
        login_input = request.POST.get("login_input", "").strip()
        password = request.POST.get("password", "")

        if not login_input:
            messages.error(request, "Email is required.")
            return render(request, "accounts/login.html")

        if not password:
            messages.error(request, "Password is required.")
            return render(request, "accounts/login.html")

        user = User.objects.filter(
        Q(username__iexact=login_input) |Q(email__iexact=login_input)
        ).first()

        if user is None:
            messages.error(request, "Invalid username/email or password.")
            return render(request, "accounts/login.html")

        authenticated_user = authenticate(
            request,
            username=user.username,
            password=password
        )

        if authenticated_user is None:
            messages.error(request,"Invalid username/email or password.")
            return render(request, "accounts/login.html")

        if authenticated_user.is_blocked:
            messages.error(request,"Your account has been blocked.")
            return render(request, "accounts/login.html")

        login(request, authenticated_user)
        return redirect("home")
    
    return render(request, "accounts/login.html")