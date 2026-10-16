from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render, get_object_or_404

from orders.models import Order


@login_required
def user_order_list(request):
    search_query = request.GET.get("search", "").strip()

    # Display only the logged-in user's orders, newest first.
    orders = Order.objects.filter(
        user=request.user
    ).order_by("-created_at")

    # Search by order number.
    if search_query:
        orders = orders.filter(
            Q(order_number__icontains=search_query)
        )

    # Display 10 orders per page.
    paginator = Paginator(orders, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "orders": page_obj,
        "page_obj": page_obj,
        "search_query": search_query,
    }

    return render(
        request,
        "userside/my_orders.html",
        context,
    )


@login_required
def user_order_detail(request, order_number):
    # A user can access only their own order.
    order = get_object_or_404(
        Order.objects
        .select_related("user", "order_address")
        .prefetch_related(
            "items__product_variant",
            "status_history",
        ),
        order_number=order_number,
        user=request.user,
    )

    context = {
        "order": order,
    }

    return render(
        request,
        "userside/order_detail.html",
        context,
    )