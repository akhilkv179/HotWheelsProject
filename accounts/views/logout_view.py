from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.http import HttpResponseNotAllowed
from django.views.decorators.cache import never_cache

@never_cache
def logout_view(request):

    if not request.user.is_authenticated:
        return redirect("login")

    if request.method == "POST":

        logout(request)

        messages.success(request, "You have been logged out successfully")

        return redirect("login")

    return HttpResponseNotAllowed(["POST"])