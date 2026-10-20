from decimal import Decimal

from django.db.models import Sum
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render
from django.utils import timezone

from accounts.models import User
from orders.models import Order
from products.models import Product


# Check whether the frontend expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Display the admin dashboard with summary metrics on sales, revenue, and inventory.
def admin_dashboard(request):

    # Allow only GET requests to view dashboard information.
    if request.method != "GET":
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "Only GET requests are allowed.",
            }, status=405)

        return HttpResponseNotAllowed(["GET"])

    # Get today's date and the first day of the current month.
    today = timezone.localdate()
    month_start = today.replace(day=1)

    # Get delivered orders for revenue calculations.
    delivered_orders = Order.objects.filter(status="delivered")

    # Calculate total revenue from delivered orders.
    total_revenue = delivered_orders.aggregate(
        total=Sum("total_amount")
    )["total"] or Decimal("0.00")

    # Count all orders.
    total_orders = Order.objects.count()

    # Count active, non-admin customers.
    total_customers = User.objects.filter(
        is_staff=False,
        is_superuser=False,
        is_blocked=False
    ).count()

    # Count products that have not been deleted.
    total_products = Product.objects.filter(
        is_deleted=False
    ).count()

    # Calculate revenue from delivered orders created this month.
    monthly_revenue = delivered_orders.filter(
        created_at__date__gte=month_start,
        created_at__date__lte=today
    ).aggregate(
        total=Sum("total_amount")
    )["total"] or Decimal("0.00")

    # Retrieve the ten most recent orders with their associated users.
    recent_orders = Order.objects.select_related(
        "user"
    ).order_by("-created_at")[:10]

    # Collect dashboard values for the HTML template.
    context = {
        "total_revenue": total_revenue,
        "total_orders": total_orders,
        "total_customers": total_customers,
        "total_products": total_products,
        "monthly_revenue": monthly_revenue,
        "recent_orders": recent_orders,
    }

    # Return dashboard metrics as JSON when requested.
    if wants_json(request):
        return JsonResponse({
            "success": True,
            "dashboard": {
                "total_revenue": str(total_revenue),
                "total_orders": total_orders,
                "total_customers": total_customers,
                "total_products": total_products,
                "monthly_revenue": str(monthly_revenue),
                "recent_orders": [
                    {
                        "id": order.pk,
                        "status": order.status,
                        "total_amount": str(order.total_amount),
                        "created_at": order.created_at.isoformat(),
                        "username": order.user.username,
                    }
                    for order in recent_orders
                ],
            },
        }, status=200)

    # Display the existing admin dashboard page.
    return render(
        request,
        "admin_panel/admin_dashboard.html",
        context
    )