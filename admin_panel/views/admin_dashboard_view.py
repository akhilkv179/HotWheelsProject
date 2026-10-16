from decimal import Decimal

from django.db.models import Sum
from django.shortcuts import render
from django.utils import timezone

from accounts.models import User
from orders.models import Order
from products.models import Product


def admin_dashboard(request):
    today = timezone.localdate()
    month_start = today.replace(day=1)

    delivered_orders = Order.objects.filter(status="delivered")

    total_revenue = delivered_orders.aggregate(
        total=Sum("total_amount")
    )["total"] or Decimal("0.00")

    total_orders = Order.objects.count()

    total_customers = User.objects.filter(
        is_staff=False,
        is_superuser=False,
        is_blocked=False
    ).count()

    total_products = Product.objects.filter(
        is_deleted=False
    ).count()

    monthly_revenue = delivered_orders.filter(
        created_at__date__gte=month_start,
        created_at__date__lte=today
    ).aggregate(
        total=Sum("total_amount")
    )["total"] or Decimal("0.00")

    recent_orders = Order.objects.select_related(
        "user"
    ).order_by("-created_at")[:10]

    context = {
        "total_revenue": total_revenue,
        "total_orders": total_orders,
        "total_customers": total_customers,
        "total_products": total_products,
        "monthly_revenue": monthly_revenue,
        "recent_orders": recent_orders,
    }

    return render(
        request,
        "admin_panel/admin_dashboard.html",
        context
    )