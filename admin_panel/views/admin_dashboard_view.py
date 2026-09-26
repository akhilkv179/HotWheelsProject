from django.shortcuts import render
from admin_panel.decorators import admin_required


@admin_required
def admin_dashboard(request):
    return render(
        request,
        "admin_panel/admin_dashboard.html"
    ) 