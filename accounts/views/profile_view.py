from django.contrib.auth.decorators import login_required
from django.shortcuts import render,redirect
from django.contrib import messages
from ..models import User
from django.views.decorators.cache import never_cache

@never_cache
@login_required
def profile_view(request):

    if not request.user.is_authenticated:
        return redirect("login")

   
    return render(request, "accounts/profile.html")


