from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from ..models import User


# Authenticate customers using email or username and password.
@never_cache
def login_view(request):

    if request.user.is_authenticated:
        if request.headers.get("Accept", "").find("application/json") != -1:
            return JsonResponse({
                "success": True,
                "message": "You are already logged in.",
                "redirect_url": "/"
            }, status=200)
        return redirect("home")

    # Process submitted login details.
    if request.method == "POST":
        login_input = request.POST.get("login_input", "").strip()
        password = request.POST.get("password", "")

        # Check whether the login identifier was provided.
        if not login_input:
            if request.headers.get("Accept", "").find("application/json") != -1:
                return JsonResponse({
                    "success": False,
                    "message": "Email or username is required."
                }, status=400)

            messages.error(request, "Email or username is required.")
            return render(request, "accounts/login.html", status=400)

        # Check whether the password was provided.
        if not password:
            if request.headers.get("Accept", "").find("application/json") != -1:
                return JsonResponse({
                    "success": False,
                    "message": "Password is required."
                }, status=400)

            messages.error(request, "Password is required.")
            return render(request, "accounts/login.html", status=400)

        # Find the customer using either their username or email.
        user = User.objects.filter(
            Q(username__iexact=login_input) | Q(email__iexact=login_input)
        ).first()

        # Use a generic error message to avoid revealing account details.
        if user is None:
            if request.headers.get("Accept", "").find("application/json") != -1:
                return JsonResponse({
                    "success": False,
                    "message": "Invalid username/email or password."
                }, status=401)

            messages.error(request, "Invalid username/email or password.")
            return render(request, "accounts/login.html", status=401)

        # Verify the supplied password.
        authenticated_user = authenticate(
            request,
            username=user.username,
            password=password
        )

        if authenticated_user is None:
            if request.headers.get("Accept", "").find("application/json") != -1:
                return JsonResponse({
                    "success": False,
                    "message": "Invalid username/email or password."
                }, status=401)

            messages.error(request, "Invalid username/email or password.")
            return render(request, "accounts/login.html", status=401)

        # Prevent blocked accounts from signing in.
        if authenticated_user.is_blocked:
            if request.headers.get("Accept", "").find("application/json") != -1:
                return JsonResponse({
                    "success": False,
                    "message": "Your account has been blocked."
                }, status=403)

            messages.error(request, "Your account has been blocked.")
            return render(request, "accounts/login.html", status=403)

        # Log in the authenticated customer.
        login(request, authenticated_user)

        if request.headers.get("Accept", "").find("application/json") != -1:
            return JsonResponse({
                "success": True,
                "message": "Login successful.",
                "redirect_url": "/"
            }, status=200)

        return redirect("home")

    # Display the login page for normal GET requests.
    return render(request, "accounts/login.html")