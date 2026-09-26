from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from accounts.models import User
from admin_panel.decorators import admin_required


@admin_required
def user_list(request):
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

    return render(
        request,
        "admin_panel/user_list.html",
        {
            "page_obj": page_obj,
            "search_query": search_query,
        },
    )