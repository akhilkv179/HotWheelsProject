from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.cache import never_cache


# Display the customer profile dashboard with personal account information.
@never_cache
@login_required
def profile_view(request):

    # Allow only GET requests for viewing the profile.
    if request.method != "GET":
        if "application/json" in request.headers.get("Accept", ""):
            return JsonResponse({
                "success": False,
                "message": "Only GET requests are allowed.",
            }, status=405)

        return HttpResponseNotAllowed(["GET"])

    # Return profile data when the frontend requests JSON.
    if "application/json" in request.headers.get("Accept", ""):
        user = request.user

        return JsonResponse({
            "success": True,
            "profile": {
                "username": user.username,
                "email": user.email,
                "phone": user.phone,
            },
        }, status=200)

    # Display the existing profile page.
    return render(request, "accounts/profile.html")