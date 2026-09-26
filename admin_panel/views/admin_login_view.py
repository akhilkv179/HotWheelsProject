from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect

from accounts.models import User


def admin_login(request):
    if request.method == "POST":
        u_name = request.POST.get("username", "").strip()
        p_word = request.POST.get("password", "")

        username = u_name

        if "@" in u_name:
            user = User.objects.filter(email__iexact=u_name).first()

            if user:
                username = user.username
            else:
                username = None

        if username:
            authenticated_user = authenticate(
                request,
                username=username,
                password=p_word
            )
        else:
            authenticated_user = None

        if authenticated_user is not None:
            if not authenticated_user.is_active:
                messages.error(request, "This account is inactive.")

            elif not authenticated_user.is_staff:
                messages.error(request, "You do not have admin access.")

            else:
                login(request, authenticated_user)
                return redirect("admin_dashboard")

        else:
            messages.error(request, "Invalid username or password.")

    return render(request, "admin_panel/admin_login.html")