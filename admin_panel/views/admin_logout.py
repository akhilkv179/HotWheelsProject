from django.contrib.auth import logout
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.cache import never_cache

from admin_panel.decorators import admin_required


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Log out the current administrator and redirect to the admin login page.
@never_cache
@admin_required
def admin_logout(request):

    if request.method != "POST":
        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Logout requires a POST request."
                },
                status=405
            )

        return HttpResponseNotAllowed(["POST"])

    if not request.user.is_authenticated:
        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": "You are not logged in.",
                    "redirect_url": reverse("admin_login")
                },
                status=401
            )

        return redirect("admin_login")

    logout(request)

    if wants_json(request):
        return JsonResponse(
            {
                "success": True,
                "message": "Logged out successfully.",
                "redirect_url": reverse("admin_login")
            },
            status=200
        )

    return redirect("admin_login")