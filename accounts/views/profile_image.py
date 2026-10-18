from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.views.decorators.cache import never_cache

@never_cache
@login_required
def change_profile_image(request):

    if not request.user.is_authenticated:
            return redirect("login")
    

    user = request.user

    if request.method == "POST":

        profile_image = request.FILES.get("profile_image")

        if not profile_image:
            messages.error(request,"Please select a profile picture")
            return render(request,"accounts/change_profile_image.html")

        user.profile_image = profile_image
        user.save()

        messages.success(request,"Profile picture updated successfully")
        return redirect("profile")

    return render(request,"accounts/change_profile_image.html" )