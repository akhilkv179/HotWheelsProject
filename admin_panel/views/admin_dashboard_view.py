
from decimal import Decimal

from django.db.models import Sum, Count
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render
from django.utils import timezone

from accounts.models import User
from orders.models import Order, OrderItem
from products.models import Product
from payments.models import Refund


# Check whether the frontend expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Display the admin dashboard with sales, revenue, inventory and order metrics.
def admin_dashboard(request):

    # Allow only GET requests.
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

    # Get delivered orders.
    delivered_orders = Order.objects.filter(status__iexact="delivered")

    # Get all non-cancelled orders.
    active_orders = Order.objects.exclude(status__iexact="cancelled")

    # --------------------------------------------------
    # 1. SALES AND REVENUE
    # --------------------------------------------------

    # Total revenue from delivered orders.
    total_revenue = delivered_orders.aggregate(
        total=Sum("total_amount")
    )["total"] or Decimal("0.00")

    # Total sales: number of delivered orders.
    total_sales = delivered_orders.count()

    # Total orders: all orders regardless of status.
    total_orders = Order.objects.count()

    # Total discounts recorded on non-cancelled orders.
    total_discounts = active_orders.aggregate(
        total=Sum("discount_amount")
    )["total"] or Decimal("0.00")

    # Coupon discounts recorded on orders with a coupon.
    coupon_discounts = active_orders.filter(
        coupon__isnull=False
    ).aggregate(
        total=Sum("discount_amount")
    )["total"] or Decimal("0.00")

    # --------------------------------------------------
    # 2. PRODUCT SALES
    # --------------------------------------------------

    # Total quantity of active items in delivered orders.
    product_sales = OrderItem.objects.filter(
        order__in=delivered_orders,
        item_status="active"
    ).aggregate(
        total=Sum("quantity")
    )["total"] or 0

    # --------------------------------------------------
    # 3. REFUNDS
    # --------------------------------------------------

    # Total amount recorded in refund records.
    total_refunds = Refund.objects.aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")

    # --------------------------------------------------
    # 4. ORDER STATUS COUNTS
    # --------------------------------------------------

    # Count orders separately for each status.
    order_status_counts = {
        item["status"]: item["count"]
        for item in Order.objects.values("status").annotate(
            count=Count("id")
        )
    }

    # --------------------------------------------------
    # 5. PAYMENT METHOD COUNTS
    # --------------------------------------------------

    # Count orders according to their selected payment method.
    razorpay_count = Order.objects.filter(
        delivery_method__iexact="Razorpay"
    ).count()

    cod_count = Order.objects.filter(
        delivery_method__iexact="Cash on Delivery"
    ).count()

    wallet_count = Order.objects.filter(
        delivery_method__iexact="Wallet"
    ).count()

    payment_counts = {
        "razorpay": razorpay_count,
        "cod": cod_count,
        "wallet": wallet_count,
    }

    # --------------------------------------------------
    # 6. EXISTING DASHBOARD METRICS
    # --------------------------------------------------

    # Count all active non-admin customers.
    total_customers = User.objects.filter(
        is_staff=False,
        is_superuser=False,
        is_blocked=False
    ).count()

    # Count products that have not been deleted.
    total_products = Product.objects.filter(
        is_deleted=False
    ).count()

    # Calculate monthly revenue from delivered orders.
    monthly_revenue = delivered_orders.filter(
        created_at__date__gte=month_start,
        created_at__date__lte=today
    ).aggregate(
        total=Sum("total_amount")
    )["total"] or Decimal("0.00")

    # Retrieve the ten most recent orders.
    recent_orders = Order.objects.select_related(
        "user"
    ).order_by("-created_at")[:10]

    # --------------------------------------------------
    # 7. TEMPLATE CONTEXT
    # --------------------------------------------------

    context = {
        "total_revenue": total_revenue,
        "total_sales": total_sales,
        "total_orders": total_orders,
        "product_sales": product_sales,
        "total_discounts": total_discounts,
        "coupon_discounts": coupon_discounts,
        "total_refunds": total_refunds,

        "order_status_counts": order_status_counts,
        "payment_counts": payment_counts,

        "total_customers": total_customers,
        "total_products": total_products,
        "monthly_revenue": monthly_revenue,
        "recent_orders": recent_orders,
    }

    # --------------------------------------------------
    # 8. JSON RESPONSE
    # --------------------------------------------------

    if wants_json(request):
        return JsonResponse({
            "success": True,
            "dashboard": {
                "total_revenue": str(total_revenue),
                "total_sales": total_sales,
                "total_orders": total_orders,
                "product_sales": product_sales,
                "total_discounts": str(total_discounts),
                "coupon_discounts": str(coupon_discounts),
                "total_refunds": str(total_refunds),

                "order_status_counts": order_status_counts,
                "payment_counts": payment_counts,

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

    # Display the admin dashboard page.
    return render(
        request,
        "admin_panel/admin_dashboard.html",
        context
    )
