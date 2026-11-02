
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.cache import never_cache


# Display the admin profile with personal account information.
@never_cache
def admin_profile_view(request):

    # Allow only GET requests for viewing the profile.
    if request.method != "GET":
        if "application/json" in request.headers.get("Accept", ""):
            return JsonResponse({
                "success": False,
                "message": "Only GET requests are allowed.",
            }, status=405)

        return HttpResponseNotAllowed(["GET"])

    # Check whether the user is authenticated.
    if not request.user.is_authenticated:
        if "application/json" in request.headers.get("Accept", ""):
            return JsonResponse({
                "success": False,
                "message": "Authentication required.",
                "redirect_url": reverse("admin_login"),
            }, status=401)

        return redirect("admin_login")

    # Allow access only to active staff members.
    if not request.user.is_active or not request.user.is_staff:
        if "application/json" in request.headers.get("Accept", ""):
            return JsonResponse({
                "success": False,
                "message": "You do not have admin access.",
            }, status=403)

        return redirect("admin_login")

    # Return admin profile data when the frontend requests JSON.
    if "application/json" in request.headers.get("Accept", ""):
        user = request.user

        return JsonResponse({
            "success": True,
            "profile": {
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone": user.phone,
                "profile_image": (
                    request.build_absolute_uri(user.profile_image.url)
                    if user.profile_image
                    else None
                ),
                "is_superuser": user.is_superuser,
            },
        }, status=200)

    # Display the admin profile page.
    return render(request, "admin_panel/admin_profile.html")
