from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect

from accounts.models import User
from admin_panel.decorators import admin_required


# Toggle a customer account active or blocked status from the admin panel.
@admin_required
def toggle_user_status(request, user_id):

    if request.method != "POST":
        if "application/json" in request.headers.get("Accept", ""):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Only POST requests are allowed."
                },
                status=405
            )

        return HttpResponseNotAllowed(["POST"])

    user = get_object_or_404(User, id=user_id)

    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])

    if "application/json" in request.headers.get("Accept", ""):
        return JsonResponse(
            {
                "success": True,
                "message": (
                    "User activated successfully."
                    if user.is_active
                    else "User blocked successfully."
                ),
                "user_id": user.id,
                "is_active": user.is_active
            },
            status=200
        )

    return redirect("user_list")