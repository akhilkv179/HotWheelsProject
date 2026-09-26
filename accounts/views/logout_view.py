from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect


def logout_view(request):

    if request.method == "POST":


        logout(request)

        messages.success(request,"You have been logged out successfully")

        return redirect("login")
    return redirect("profile")

