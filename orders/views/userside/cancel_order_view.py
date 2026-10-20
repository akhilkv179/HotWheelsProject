
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect

from orders.models import Order, OrderItem, OrderStatusHistory
from products.models import ProductVariant


# Check whether the client expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Cancel an order or a specific order item and restore inventory stock.
@login_required
def cancel_order(request, order_number, item_id):
    # Only allow POST requests to cancel an order or item.
    if request.method != "POST":
        if wants_json(request):
            return JsonResponse(
                {"error": "Only POST requests are allowed."},
                status=405,
            )
        return HttpResponseNotAllowed(["POST"])

    reason = request.POST.get("reason", "").strip()

    with transaction.atomic():
        # Find and lock the order belonging to the logged-in user.
        order = get_object_or_404(
            Order.objects.select_for_update(),
            order_number=order_number,
            user=request.user,
        )

        # Check whether the order is still eligible for cancellation.
        if order.status not in ["pending", "confirmed"]:
            error_message = "This order can no longer be cancelled."

            if wants_json(request):
                return JsonResponse(
                    {"error": error_message},
                    status=400,
                )

            messages.error(request, error_message)
            return redirect(
                "user_order_detail",
                order_number=order.order_number,
            )

        # Find and lock the selected item in this order.
        item = get_object_or_404(
            OrderItem.objects.select_for_update(),
            id=item_id,
            order=order,
        )

        # Prevent cancelling an item that is already processed.
        if item.item_status != "active":
            error_message = "This item can no longer be cancelled."

            if wants_json(request):
                return JsonResponse(
                    {"error": error_message},
                    status=400,
                )

            messages.error(request, error_message)
            return redirect(
                "user_order_detail",
                order_number=order.order_number,
            )

        # Lock the product variant before restoring its stock.
        variant = get_object_or_404(
            ProductVariant.objects.select_for_update(),
            id=item.product_variant_id,
        )

        variant.stock_quantity += item.quantity
        variant.save(
            update_fields=["stock_quantity", "updated_at"]
        )

        # Mark the item as cancelled to prevent duplicate stock restoration.
        item.item_status = "cancelled"
        item.save(update_fields=["item_status"])

        # Recalculate totals using the remaining active items.
        remaining_items = order.items.filter(
            item_status="active"
        )

        remaining_subtotal = remaining_items.aggregate(
            total=Sum("total_price")
        )["total"] or Decimal("0.00")

        remaining_discount = remaining_items.aggregate(
            total=Sum("discount_amount")
        )["total"] or Decimal("0.00")

        order.subtotal = remaining_subtotal
        order.discount_amount = remaining_discount

        if not remaining_items.exists():
            # Mark the order as cancelled when no active items remain.
            order.status = "cancelled"
            # order.shipping_amount = Decimal("0.00")
            # order.total_amount = Decimal("0.00")

            OrderStatusHistory.objects.create(
                order=order,
                status="cancelled",
            )

            message = "All items have been cancelled."

        else:
            # Recalculate shipping using the existing checkout rule.
            order.shipping_amount = (
                Decimal("0.00")
                if remaining_subtotal >= Decimal("1000.00")
                else Decimal("50.00")
            )

            order.total_amount = (
                order.subtotal
                - order.discount_amount
                + order.shipping_amount
            )

            message = "The selected item has been cancelled."

        # Save the updated order totals and status when applicable.
        update_fields = [
            "subtotal",
            "discount_amount",
            "shipping_amount",
            "total_amount",
            "updated_at",
        ]

        if order.status == "cancelled":
            update_fields.append("status")

        order.save(update_fields=update_fields)

    # Return a JSON response for API clients.
    if wants_json(request):
        return JsonResponse(
            {
                "message": message,
                "order_number": order.order_number,
                "order_status": order.status,
                "item_id": item.id,
                "item_status": item.item_status,
                "subtotal": str(order.subtotal),
                "discount_amount": str(order.discount_amount),
                "shipping_amount": str(order.shipping_amount),
                "total_amount": str(order.total_amount),
            },
            status=200,
        )

    # Preserve the existing message and redirect for HTML requests.
    messages.success(request, message)

    return redirect(
        "user_order_detail",
        order_number=order.order_number,
    )
