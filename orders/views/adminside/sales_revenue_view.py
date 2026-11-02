
from datetime import timedelta
from decimal import Decimal

from django.core.paginator import Paginator
from django.db.models import Sum, Avg
from django.shortcuts import render
from django.utils import timezone

from orders.models import Order, OrderItem


def sales_revenue_view(request):
    """
    Display filtered sales and revenue information for administrators.
    """

    # Get the selected filter. Default to all-time data.
    date_filter = request.GET.get("filter", "all")

    # Get today's date.
    today = timezone.localdate()

    # Start with all orders.
    orders = Order.objects.all()

    # Store the selected date range.
    start_date = None
    end_date = None

    # Apply the selected date filter.
    if date_filter == "all":
        # Keep all orders without applying a date filter.
        pass

    elif date_filter == "daily":
        start_date = today
        end_date = today

    elif date_filter == "weekly":
        start_date = today - timedelta(days=today.weekday())
        end_date = today

    elif date_filter == "monthly":
        start_date = today.replace(day=1)
        end_date = today

    elif date_filter == "custom":
        start_date_input = request.GET.get("start_date")
        end_date_input = request.GET.get("end_date")

        try:
            if start_date_input:
                start_date = timezone.datetime.strptime(
                    start_date_input,
                    "%Y-%m-%d",
                ).date()

            if end_date_input:
                end_date = timezone.datetime.strptime(
                    end_date_input,
                    "%Y-%m-%d",
                ).date()

        except ValueError:
            start_date = None
            end_date = None

    # Filter orders using the selected date range.
    if start_date:
        orders = orders.filter(created_at__date__gte=start_date)

    if end_date:
        orders = orders.filter(created_at__date__lte=end_date)

    # Exclude fully cancelled orders from sales and revenue.
    revenue_orders = orders.exclude(
        status__iexact="cancelled"
    )

    # Calculate revenue and average order value.
    summary = revenue_orders.aggregate(
        total_revenue=Sum("total_amount"),
        average_order_value=Avg("total_amount"),
    )

    total_revenue = summary["total_revenue"] or Decimal("0.00")
    average_order_value = (
        summary["average_order_value"] or Decimal("0.00")
    )

    # Count unique customers who placed orders in the selected period.
    total_customers = orders.values("user").distinct().count()

    # Calculate the total quantity of active products sold.
    product_summary = OrderItem.objects.filter(
        order__in=revenue_orders,
        item_status="active",
    ).aggregate(
        total_products_sold=Sum("quantity")
    )

    total_products_sold = (
        product_summary["total_products_sold"] or 0
    )

    # Count pending orders in the selected period.
    pending_orders = orders.filter(
        status__iexact="pending"
    ).count()

    # Order records by newest first.
    ordered_revenue_orders = revenue_orders.order_by("-created_at")

    # Display 10 orders per page.
    paginator = Paginator(ordered_revenue_orders, 10)

    # Get the requested page.
    page_obj = paginator.get_page(request.GET.get("page"))

    # Preserve existing filters when navigating between pages.
    query_params = request.GET.copy()
    query_params.pop("page", None)

    context = {
        "total_revenue": total_revenue,
        "total_sales": revenue_orders.count(),
        "total_orders": orders.count(),
        "total_customers": total_customers,
        "total_products_sold": total_products_sold,
        "pending_orders": pending_orders,
        "average_order_value": average_order_value,

        # Paginated order records.
        "orders": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "query_params": query_params.urlencode(),

        "current_date": today,
        "date_filter": date_filter,
        "start_date": start_date,
        "end_date": end_date,
    }

    return render(
        request,
        "adminside/sales_revenue.html",
        context,
    )
