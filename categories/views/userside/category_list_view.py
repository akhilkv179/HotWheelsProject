from django.shortcuts import render
from categories.models import Category
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseNotAllowed


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Display active product categories with search and sorting for customers.
@login_required
def user_category_list(request):

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
    sort = request.GET.get("sort", "name_az")

    categories = Category.objects.filter(
        is_active=True,
        is_deleted=False
    )

    if search_query:
        categories = categories.filter(
            Q(name__icontains=search_query)
            | Q(description__icontains=search_query)
        )

    # Sorting
    if sort == "name_az":
        categories = categories.order_by("name")
    elif sort == "name_za":
        categories = categories.order_by("-name")
    elif sort == "newest":
        categories = categories.order_by("-created_at")
    elif sort in ("oldest", "olderst"):
        # Accept the old spelling for backward compatibility.
        sort = "oldest"
        categories = categories.order_by("created_at")
    else:
        sort = "name_az"
        categories = categories.order_by("name")

    paginator = Paginator(categories, 7)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    if wants_json(request):
        categories_data = []

        for category in page_obj:
            categories_data.append({
                "id": category.id,
                "name": category.name,
                "description": category.description,
                "image_url": (
                    category.image.url
                    if category.image
                    else None
                ),
                "created_at": category.created_at.isoformat(),
            })

        return JsonResponse(
            {
                "success": True,
                "categories": categories_data,
                "filters": {
                    "search": search_query,
                    "sort": sort,
                },
                "pagination": {
                    "current_page": page_obj.number,
                    "total_pages": paginator.num_pages,
                    "total_categories": paginator.count,
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
                    ),
                },
            },
            status=200
        )

    return render(
        request,
        "userside/category_list.html",
        {
            "page_obj": page_obj,
            "search_query": search_query,
            "sort": sort,
        }
    )