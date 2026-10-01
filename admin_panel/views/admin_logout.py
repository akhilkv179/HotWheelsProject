from django.contrib.auth import logout
from django.shortcuts import redirect
from django.views.decorators.cache import never_cache
from admin_panel.decorators import admin_required


@never_cache
@admin_required
def admin_logout(request):
    if not request.user.is_authenticated:
        return redirect("admin_login")

    
    logout(request)
    return redirect("admin_login")