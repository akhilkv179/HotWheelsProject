from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.cache import never_cache

from accounts.models import User
from admin_panel.decorators import admin_required


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Display a paginated and searchable list of registered users for administrators.
@never_cache
@admin_required
def user_list(request):

    if not request.user.is_authenticated:
        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Please log in as an administrator.",
                    "redirect_url": reverse("admin_login")
                },
                status=401
            )

        return redirect("admin_login")

    if request.method != "GET":
        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Only GET requests are allowed."
                },
                status=405
            )

        return HttpResponseNotAllowed(["GET"])

    search_query = request.GET.get("search", "").strip()

    users = User.objects.all().order_by("-date_joined")

    if search_query:
        users = users.filter(
            Q(username__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
        )

    paginator = Paginator(users, 10)

    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Take the requested page number and retrieve that page from the paginator.

    if wants_json(request):
        return JsonResponse(
            {
                "success": True,
                "search_query": search_query,
                "pagination": {
                    "current_page": page_obj.number,
                    "total_pages": paginator.num_pages,
                    "total_users": paginator.count,
                    "has_next": page_obj.has_next(),
                    "has_previous": page_obj.has_previous(),
                    "next_page": (
                        page_obj.next_page_number()
                        if page_obj.has_next()
                        else None
                    ),
                    "previous_page": (
                        page_obj.previous_page_number()
                        if page_obj.has_previous()
                        else None
                    )
                },
                "users": [
                    {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "is_active": user.is_active,
                        "date_joined": user.date_joined.isoformat()
                    }
                    for user in page_obj
                ]
            },
            status=200
        )

    return render(
        request,
        "admin_panel/user_list.html",
        {
            "page_obj": page_obj,
            "search_query": search_query,
        },
    )