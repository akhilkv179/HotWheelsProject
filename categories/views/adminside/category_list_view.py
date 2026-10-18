
from django.shortcuts import render
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils import timezone

from admin_panel.decorators import admin_required
from categories.models import Category


def category_list(request):
    search_query = request.GET.get("search", "").strip()
    sort_by = request.GET.get("sort", "newest")

    categories = Category.objects.all()

    if search_query:
        categories = categories.filter(
            Q(name__icontains=search_query)
            | Q(description__icontains=search_query)
        )

    # Sorting
    if sort_by == "name_asc":
        categories = categories.order_by("name")
    elif sort_by == "name_desc":
        categories = categories.order_by("-name")
    elif sort_by == "oldest":
        categories = categories.order_by("created_at")
    else:
        sort_by = "newest"
        categories = categories.order_by("-created_at")

    paginator = Paginator(categories, 3)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    current_time = timezone.now()

    for category in page_obj:
        offer = category.offers.filter(
            is_active=True,
            start_date__lte=current_time,
            end_date__gte=current_time
        ).order_by("-discount_value").first()

        category.current_offer = offer

    return render(
        request,
        "adminside/category_list.html",
        {
            "page_obj": page_obj,
            "search_query": search_query,
            "sort_by": sort_by,
        }
    )
