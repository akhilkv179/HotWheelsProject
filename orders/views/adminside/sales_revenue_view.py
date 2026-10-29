
from decimal import Decimal

from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum, Avg
from django.shortcuts import render
from django.utils import timezone

from orders.models import Order


# @staff_member_required(login_url="/d/admin_login/")
def sales_revenue_view(request):
    """
    Display sales and revenue summary for administrators.
    """

    # Retrieve all orders.
    orders = Order.objects.all()

    # Exclude fully cancelled orders from the initial sales calculation.
    revenue_orders = orders.exclude(status__iexact="cancelled")

    # Calculate sales and revenue summary.
    summary = revenue_orders.aggregate(
        total_revenue=Sum("total_amount"),
        average_order_value=Avg("total_amount"),
    )

    total_revenue = summary["total_revenue"] or Decimal("0.00")
    average_order_value = (
        summary["average_order_value"] or Decimal("0.00")
    )

    context = {
        "total_revenue": total_revenue,
        "total_sales": revenue_orders.count(),
        "total_orders": orders.count(),
        "average_order_value": average_order_value,
        "orders": revenue_orders.order_by("-created_at"),
        "current_date": timezone.localdate(),
    }

    return render(
        request,
        "adminside/sales_revenue.html",
        context,
    )
