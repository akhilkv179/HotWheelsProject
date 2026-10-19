from django.shortcuts import render
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils import timezone
from django.http import JsonResponse, HttpResponseNotAllowed

from admin_panel.decorators import admin_required
from categories.models import Category


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Display a searchable, sortable list of product categories for administrators.
@admin_required
def category_list(request):

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
    categories_data = []

    for category in page_obj:
        offer = category.offers.filter(
            is_active=True,
            start_date__lte=current_time,
            end_date__gte=current_time
        ).order_by("-discount_value").first()

        category.current_offer = offer

        if wants_json(request):
            categories_data.append({
                "id": category.id,
                "name": category.name,
                "description": category.description,
                "is_active": category.is_active,
                "is_deleted": category.is_deleted,
                "created_at": category.created_at.isoformat(),
                "image_url": (
                    category.image.url
                    if category.image
                    else None
                ),
                "current_offer": (
                    {
                        "id": offer.id,
                        "discount_value": str(offer.discount_value),
                        "start_date": offer.start_date.isoformat(),
                        "end_date": offer.end_date.isoformat(),
                    }
                    if offer
                    else None
                ),
            })

    if wants_json(request):
        return JsonResponse(
            {
                "success": True,
                "categories": categories_data,
                "filters": {
                    "search": search_query,
                    "sort": sort_by,
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
        "adminside/category_list.html",
        {
            "page_obj": page_obj,
            "search_query": search_query,
            "sort_by": sort_by,
        }
    )