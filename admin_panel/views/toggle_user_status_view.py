from django.shortcuts import get_object_or_404, redirect

from accounts.models import User
from admin_panel.decorators import admin_required


@admin_required
def toggle_user_status(request, user_id):
    user = get_object_or_404(User, id=user_id)

    user.is_active = not user.is_active
    user.save()

    return redirect("user_list")