
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render, redirect, get_object_or_404
from products.models import ProductVariant
from orders.models import Order, OrderStatusHistory
from django.core.exceptions import ValidationError
from wallet.services.refund_service import credit_wallet_refund


ORDER_STATUSES = [
    "pending",
    "confirmed",
    "shipped",
    "out for delivery",
    "delivered",
    "cancelled",
]


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Display a searchable and filterable list of customer orders for administrators.
@staff_member_required(login_url="/d/admin_login/")
def admin_order_list(request):
    # Allow only GET requests to retrieve the order list.
    if request.method != "GET":
        if wants_json(request):
            return JsonResponse(
                {"error": "Method not allowed."},
                status=405,
            )
        return HttpResponseNotAllowed(["GET"])

    # Read the search, status filter, and sorting options.
    search = request.GET.get("search", "").strip()
    status = request.GET.get("status", "").strip()
    sort = request.GET.get("sort", "newest")

    # Retrieve orders along with their associated users.
    orders = Order.objects.select_related("user").order_by("-created_at")

    # Search orders by order number, username, or email.
    if search:
        orders = orders.filter(
            Q(order_number__icontains=search)
            | Q(user__username__icontains=search)
            | Q(user__email__icontains=search)
        )

    # Filter orders when a valid status is selected.
    if status in ORDER_STATUSES:
        orders = orders.filter(status=status)

    # Map sorting choices to database ordering fields.
    sort_options = {
        "newest": "-created_at",
        "oldest": "created_at",
        "order_az": "order_number",
        "order_za": "-order_number",
        "total_low": "total_amount",
        "total_high": "-total_amount",
    }

    # Apply the selected sorting option.
    orders = orders.order_by(sort_options.get(sort, "-created_at"))

    # Divide the order list into pages containing 10 orders.
    paginator = Paginator(orders, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    # Return paginated order data as JSON when requested.
    if wants_json(request):
        return JsonResponse(
            {
                "orders": [
                    {
                        "order_number": order.order_number,
                        "username": order.user.username,
                        "email": order.user.email,
                        "status": order.status,
                        "total_amount": str(order.total_amount),
                        "created_at": order.created_at.isoformat(),
                    }
                    for order in page_obj
                ],
                "pagination": {
                    "current_page": page_obj.number,
                    "total_pages": paginator.num_pages,
                    "total_orders": paginator.count,
                    "has_next": page_obj.has_next(),
                    "has_previous": page_obj.has_previous(),
                },
                "filters": {
                    "search": search,
                    "status": status,
                    "sort": sort,
                },
                "order_statuses": ORDER_STATUSES,
            },
            status=200,
        )

    # Render the normal HTML order list for administrators.
    return render(
        request,
        "adminside/admin_order_list.html",
        {
            "orders": page_obj,
            "page_obj": page_obj,
            "search": search,
            "selected_status": status,
            "selected_sort": sort,
            "order_statuses": ORDER_STATUSES,
        },
        status=200,
    )


# Display detailed order information, items, address, and status history.
@staff_member_required(login_url="/d/admin_login/")
def admin_order_detail(request, order_number):
    # Allow only GET requests to retrieve order details.
    if request.method != "GET":
        if wants_json(request):
            return JsonResponse(
                {"error": "Method not allowed."},
                status=405,
            )
        return HttpResponseNotAllowed(["GET"])

    # Find the requested order and load its related information.
    order = get_object_or_404(
        Order.objects.select_related(
            "user",
            "order_address",
        ).prefetch_related(
            "items",
            "status_history",
        ),
        order_number=order_number,
    )

    # Return detailed order information as JSON when requested.
    if wants_json(request):
        return JsonResponse(
            {
                "order": {
                    "order_number": order.order_number,
                    "username": order.user.username,
                    "email": order.user.email,
                    "status": order.status,
                    "total_amount": str(order.total_amount),
                    "created_at": order.created_at.isoformat(),
                    "address": (
                        str(order.order_address)
                        if order.order_address
                        else None
                    ),
                },
                "items": [
                    {
                        "id": item.id,
                        "product_variant_id": item.product_variant_id,
                        "quantity": item.quantity,
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
                "order_statuses": ORDER_STATUSES,
            },
            status=200,
        )

    # Render the normal HTML order detail page.
    return render(
        request,
        "adminside/admin_order_detail.html",
        {
            "order": order,
            "order_statuses": ORDER_STATUSES,
        },
        status=200,
    )


# Update order status using allowed transitions and restore stock if cancelled.
@staff_member_required(login_url="/d/admin_login/")
def admin_update_order_status(request, order_number):
    # Allow order status changes only through POST requests.
    if request.method != "POST":
        if wants_json(request):
            return JsonResponse(
                {"error": "Method not allowed."},
                status=405,
            )
        return HttpResponseNotAllowed(["POST"])

    # Read and validate the requested order status.
    new_status = request.POST.get("status", "").strip()

    if new_status not in ORDER_STATUSES:
        if wants_json(request):
            return JsonResponse(
                {"error": "Invalid order status."},
                status=400,
            )

        messages.error(request, "Invalid order status.")
        return redirect(
            "admin_order_detail",
            order_number=order_number,
        )

    # Define allowed order status transitions.
    allowed_transitions = {
        "pending": ["confirmed", "cancelled"],
        "confirmed": ["shipped", "cancelled"],
        "shipped": ["out for delivery"],
        "out for delivery": ["delivered"],
        "delivered": [],
        "cancelled": [],
    }

    refund_issued = False

    # Update the order, stock, and refund atomically.
    with transaction.atomic():
        order = get_object_or_404(
            Order.objects.select_for_update(),
            order_number=order_number,
        )

        if new_status == order.status:
            if wants_json(request):
                return JsonResponse(
                    {
                        "message": "The order already has this status.",
                        "status": order.status,
                    },
                    status=200,
                )

            messages.info(
                request,
                "The order already has this status.",
            )
            return redirect(
                "admin_order_detail",
                order_number=order_number,
            )

        if new_status not in allowed_transitions.get(order.status, []):
            error_message = (
                f"Cannot change order status from "
                f"{order.status} to {new_status}."
            )

            if wants_json(request):
                return JsonResponse(
                    {"error": error_message},
                    status=400,
                )

            messages.error(request, error_message)
            return redirect(
                "admin_order_detail",
                order_number=order_number,
            )

        # Refund paid Wallet or Razorpay orders before cancellation.
        if new_status == "cancelled":
            paid_online = (
                order.delivery_method.strip().lower()
                in ("wallet", "razorpay")
                and order.payments.filter(status="paid").exists()
            )

            refund_amount = order.total_amount or 0

            if paid_online and refund_amount > 0:
                try:
                    credit_wallet_refund(
                        user=order.user,
                        amount=refund_amount,
                        transaction_id=f"ADMIN-CANCEL-{order.pk}",
                        reference_id=order.order_number,
                    )
                    refund_issued = True

                except ValidationError as error:
                    error_message = (
                        error.messages[0]
                        if error.messages
                        else "The refund could not be processed."
                    )

                    if wants_json(request):
                        return JsonResponse(
                            {"error": error_message},
                            status=400,
                        )

                    messages.error(request, error_message)
                    return redirect(
                        "admin_order_detail",
                        order_number=order_number,
                    )

            # Restore stock for all remaining active order items.
            items = list(
                order.items.select_for_update().all()
            )

            for item in items:
                # Skip items whose stock has already been restored.
                if item.item_status != "active":
                    continue

                variant = get_object_or_404(
                    ProductVariant.objects.select_for_update(),
                    id=item.product_variant_id,
                )

                variant.stock_quantity += item.quantity
                variant.save(
                    update_fields=["stock_quantity", "updated_at"]
                )

                item.item_status = "cancelled"
                item.save(update_fields=["item_status"])

        # Save the new order status.
        order.status = new_status
        order.save(update_fields=["status", "updated_at"])

        # Record the change in order status history.
        OrderStatusHistory.objects.create(
            order=order,
            status=new_status,
        )

    # Prepare a success message after the transaction completes.
    success_message = "Order status updated successfully."

    if refund_issued:
        success_message += (
            " The refund has been credited to the customer's wallet."
        )

    if wants_json(request):
        return JsonResponse(
            {
                "message": success_message,
                "order_number": order.order_number,
                "status": order.status,
            },
            status=200,
        )

    messages.success(request, success_message)
    return redirect(
        "admin_order_detail",
        order_number=order_number,
    )
