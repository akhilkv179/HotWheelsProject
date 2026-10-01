from django.shortcuts import render,redirect
from admin_panel.decorators import admin_required
from django.views.decorators.cache import never_cache



@never_cache
@admin_required
def admin_dashboard(request):
    
     
    return render(
        request,
        "admin_panel/admin_dashboard.html"
    ) 