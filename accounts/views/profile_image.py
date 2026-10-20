from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.cache import never_cache


# Check whether the frontend expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Upload and update the profile avatar image for the logged-in user.
@never_cache
@login_required
def change_profile_image(request):

    # Allow only GET and POST requests.
    if request.method not in ["GET", "POST"]:
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "Only GET and POST requests are allowed.",
            }, status=405)

        return HttpResponseNotAllowed(["GET", "POST"])

    user = request.user

    if request.method == "POST":

        # Get the uploaded profile image from the request.
        profile_image = request.FILES.get("profile_image")

        # Check whether the user selected an image.
        if not profile_image:
            if wants_json(request):
                return JsonResponse({
                    "success": False,
                    "message": "Please select a profile picture.",
                }, status=400)

            messages.error(request, "Please select a profile picture.")
            return render(
                request,
                "accounts/change_profile_image.html",
                status=400,
            )

        # Save the uploaded image to the user's profile.
        user.profile_image = profile_image
        user.save()

        # Return JSON when the frontend expects it.
        if wants_json(request):
            return JsonResponse({
                "success": True,
                "message": "Profile picture updated successfully.",
                "redirect_url": reverse("profile"),
            }, status=200)

        messages.success(
            request,
            "Profile picture updated successfully.",
        )
        return redirect("profile")

    # Display the profile-image upload page.
    return render(request, "accounts/change_profile_image.html")