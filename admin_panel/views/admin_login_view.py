from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.cache import never_cache

from accounts.models import User


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Authenticate and log in admin and staff members into the admin portal.
@never_cache
def admin_login(request):

    if request.method not in ["GET", "POST"]:
        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Method not allowed."
                },
                status=405
            )

        return HttpResponseNotAllowed(["GET", "POST"])

    if request.user.is_authenticated and request.user.is_staff:
        if wants_json(request):
            return JsonResponse(
                {
                    "success": True,
                    "message": "You are already logged in.",
                    "redirect_url": reverse("admin_dashboard")
                },
                status=200
            )

        return redirect("admin_dashboard")

    if request.method == "POST":
        u_name = request.POST.get("username", "").strip()
        p_word = request.POST.get("password", "")

        if not u_name or not p_word:
            if wants_json(request):
                return JsonResponse(
                    {
                        "success": False,
                        "message": "Username/email and password are required."
                    },
                    status=400
                )

            messages.error(
                request,
                "Username/email and password are required."
            )
            return render(request, "admin_panel/admin_login.html")

        username = u_name

        if "@" in u_name:
            user = User.objects.filter(
                email__iexact=u_name
            ).first()

            if user:
                username = user.username
            else:
                username = None

        if username:
            authenticated_user = authenticate(
                request,
                username=username,
                password=p_word
            )
        else:
            authenticated_user = None

        if authenticated_user is not None:
            if not authenticated_user.is_active:
                error_message = "This account is inactive."

            elif not authenticated_user.is_staff:
                error_message = "You do not have admin access."

            else:
                login(request, authenticated_user)

                if wants_json(request):
                    return JsonResponse(
                        {
                            "success": True,
                            "message": "Login successful.",
                            "redirect_url": reverse("admin_dashboard")
                        },
                        status=200
                    )

                return redirect("admin_dashboard")

        else:
            error_message = "Invalid username or password."

        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": error_message
                },
                status=401
            )

        messages.error(request, error_message)

    if wants_json(request):
        return JsonResponse(
            {
                "success": True,
                "message": "Admin login page is ready."
            },
            status=200
        )

    return render(request, "admin_panel/admin_login.html")