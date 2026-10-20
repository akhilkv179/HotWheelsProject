from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.http import HttpResponseNotAllowed, JsonResponse
from django.views.decorators.cache import never_cache


# Log out the currently authenticated user and end their session.
@never_cache
def logout_view(request):

    # Redirect unauthenticated users to the login page.
    if not request.user.is_authenticated:
        if request.headers.get("Accept", "").find("application/json") != -1:
            return JsonResponse({
                "success": False,
                "message": "You are not logged in.",
                "redirect_url": "/login/"
            }, status=401)

        return redirect("login")

    # Allow logout only through POST requests.
    if request.method != "POST":
        if request.headers.get("Accept", "").find("application/json") != -1:
            return JsonResponse({
                "success": False,
                "message": "Only POST requests are allowed."
            }, status=405)

        return HttpResponseNotAllowed(["POST"])

    # End the user's authenticated session.
    logout(request)

    # Return JSON for frontend requests expecting JSON.
    if request.headers.get("Accept", "").find("application/json") != -1:
        return JsonResponse({
            "success": True,
            "message": "You have been logged out successfully.",
            "redirect_url": "/login/"
        }, status=200)

    # Preserve the existing Django messages and redirect behavior.
    messages.success(request, "You have been logged out successfully")
    return redirect("login")