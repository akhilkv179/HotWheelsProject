from django.contrib.auth.decorators import login_required
from django.shortcuts import render,redirect
from django.contrib import messages
from ..models import User


@login_required
def profile_view(request):
    return render(request, "accounts/profile.html")


