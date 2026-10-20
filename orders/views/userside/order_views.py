
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render, get_object_or_404

from orders.models import Order


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Display a paginated list of orders placed by the logged-in customer.
@login_required
def user_order_list(request):
    # Allow only GET requests to retrieve the order list.
    if request.method != "GET":
        if wants_json(request):
            return JsonResponse(
                {"error": "Only GET requests are allowed."},
                status=405,
            )
        return HttpResponseNotAllowed(["GET"])

    # Read the optional search term from the request.
    search_query = request.GET.get("search", "").strip()

    # Display only the logged-in user's orders, newest first.
    orders = Order.objects.filter(
        user=request.user
    ).order_by("-created_at")

    # Filter orders by order number when a search term is provided.
    if search_query:
        orders = orders.filter(
            Q(order_number__icontains=search_query)
        )

    # Divide the orders into pages containing ten orders each.
    paginator = Paginator(orders, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    # Return paginated order data to JSON clients.
    if wants_json(request):
        return JsonResponse(
            {
                "orders": [
                    {
                        "order_number": order.order_number,
                        "status": order.status,
                        "subtotal": str(order.subtotal),
                        "discount_amount": str(order.discount_amount),
                        "shipping_amount": str(order.shipping_amount),
                        "total_amount": str(order.total_amount),
                        "created_at": order.created_at.isoformat(),
                    }
                    for order in page_obj.object_list
                ],
                "pagination": {
                    "current_page": page_obj.number,
                    "total_pages": paginator.num_pages,
                    "total_orders": paginator.count,
                    "has_previous": page_obj.has_previous(),
                    "has_next": page_obj.has_next(),
                },
                "search_query": search_query,
            },
            status=200,
        )

    # Preserve the existing context for the HTML template.
    context = {
        "orders": page_obj,
        "page_obj": page_obj,
        "search_query": search_query,
    }

    return render(
        request,
        "userside/my_orders.html",
        context,
        status=200,
    )


# Display detailed summary and tracking information for a customer's order.
@login_required
def user_order_detail(request, order_number):
    # Allow only GET requests to retrieve order details.
    if request.method != "GET":
        if wants_json(request):
            return JsonResponse(
                {"error": "Only GET requests are allowed."},
                status=405,
            )
        return HttpResponseNotAllowed(["GET"])

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

    # Return the order summary and tracking history to JSON clients.
    if wants_json(request):
        return JsonResponse(
            {
                "order": {
                    "order_number": order.order_number,
                    "status": order.status,
                    "subtotal": str(order.subtotal),
                    "discount_amount": str(order.discount_amount),
                    "shipping_amount": str(order.shipping_amount),
                    "total_amount": str(order.total_amount),
                    "delivery_method": order.delivery_method,
                    "created_at": order.created_at.isoformat(),
                },
                "items": [
                    {
                        "id": item.id,
                        "product_name": item.product_name,
                        "product_variant_id": item.product_variant_id,
                        "quantity": item.quantity,
                        "unit_price": str(item.unit_price),
                        "discount_amount": str(item.discount_amount),
                        "total_price": str(item.total_price),
                        "item_status": item.item_status,
                    }
                    for item in order.items.all()
                ],
                "status_history": [
                    {
                        "status": history.status,
                    }
                    for history in order.status_history.all()
                ],
            },
            status=200,
        )

    # Preserve the existing context for the HTML template.
    context = {
        "order": order,
    }

    return render(
        request,
        "userside/order_detail.html",
        context,
        status=200,
    )
