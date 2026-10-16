
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from products.models import ProductVariant

from orders.models import Order, OrderStatusHistory


ORDER_STATUSES = [
    "pending",
    "confirmed",
    "shipped",
    "out_for_delivery",
    "delivered",
    "cancelled",
]


@staff_member_required
def admin_order_list(request):
    search = request.GET.get("search", "").strip()
    status = request.GET.get("status", "").strip()
    sort = request.GET.get("sort", "newest")

    orders = Order.objects.select_related("user").order_by("-created_at")

    if search:
        orders = orders.filter(
            Q(order_number__icontains=search)
            | Q(user__username__icontains=search)
            | Q(user__email__icontains=search)
        )

    if status in ORDER_STATUSES:
        orders = orders.filter(status=status)

    sort_options = {
        "newest": "-created_at",
        "oldest": "created_at",
        "order_az": "order_number",
        "order_za": "-order_number",
        "total_low": "total_amount",
        "total_high": "-total_amount",
    }

    orders = orders.order_by(sort_options.get(sort, "-created_at"))

    paginator = Paginator(orders, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

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
    )


@staff_member_required
def admin_order_detail(request, order_number):
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

    return render(
        request,
        "adminside/admin_order_detail.html",
        {
            "order": order,
            "order_statuses": ORDER_STATUSES,
        },
    )


@staff_member_required
@require_POST
def admin_update_order_status(request, order_number):
    new_status = request.POST.get("status", "").strip()

    if new_status not in ORDER_STATUSES:
        messages.error(request, "Invalid order status.")
        return redirect("admin_order_detail", order_number=order_number)

    allowed_transitions = {
        "pending": ["confirmed", "cancelled"],
        "confirmed": ["shipped", "cancelled"],
        "shipped": ["out_for_delivery"],
        "out_for_delivery": ["delivered"],
        "delivered": [],
        "cancelled": [],
    }

    with transaction.atomic():
        order = get_object_or_404(
            Order.objects.select_for_update(),
            order_number=order_number,
        )

        if new_status == order.status:
            messages.info(
                request,
                "The order already has this status.",
            )
            return redirect(
                "admin_order_detail",
                order_number=order_number,
            )

        if new_status not in allowed_transitions.get(order.status, []):
            messages.error(
                request,
                f"Cannot change order status from "
                f"{order.status} to {new_status}.",
            )
            return redirect(
                "admin_order_detail",
                order_number=order_number,
            )

        # Restore stock when the admin cancels the entire order.
        if new_status == "cancelled":
            items = list(
                order.items.select_for_update().all()
            )

            for item in items:
                # Skip items whose stock has already been handled.
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

        order.status = new_status
        order.save(update_fields=["status", "updated_at"])

        OrderStatusHistory.objects.create(
            order=order,
            status=new_status,
        )

    messages.success(
        request,
        "Order status updated successfully.",
    )
    return redirect(
        "admin_order_detail",
        order_number=order_number,
    )
