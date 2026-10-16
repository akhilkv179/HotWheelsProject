from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from orders.models import Order, OrderItem, OrderStatusHistory
from products.models import ProductVariant


@login_required
@require_POST
def cancel_order(request, order_number, item_id):
    reason = request.POST.get("reason", "").strip()

    with transaction.atomic():
        order = get_object_or_404(
            Order.objects.select_for_update(),
            order_number=order_number,
            user=request.user,
        )

        if order.status not in ["pending", "confirmed"]:
            messages.error(
                request,
                "This order can no longer be cancelled.",
            )
            return redirect(
                "user_order_detail",
                order_number=order.order_number,
            )

        item = get_object_or_404(
            OrderItem.objects.select_for_update(),
            id=item_id,
            order=order,
        )

        if item.item_status != "active":
            messages.error(
                request,
                "This item can no longer be cancelled.",
            )
            return redirect(
                "user_order_detail",
                order_number=order.order_number,
            )

        # Lock the product variant before restoring stock.
        variant = get_object_or_404(
            ProductVariant.objects.select_for_update(),
            id=item.product_variant_id,
        )

        variant.stock_quantity += item.quantity
        variant.save(
            update_fields=["stock_quantity", "updated_at"]
        )

        # Mark the item as cancelled to prevent duplicate restoration.
        item.item_status = "cancelled"
        item.save(update_fields=["item_status"])

        # Recalculate totals from the remaining active items.
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
            # Every item has been cancelled.
            order.status = "cancelled"
            order.shipping_amount = Decimal("0.00")
            order.total_amount = Decimal("0.00")

            OrderStatusHistory.objects.create(
                order=order,
                status="cancelled",
            )

            message = "All items have been cancelled."

        else:
            # Apply the same shipping rule used in checkout.
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

    messages.success(request, message)

    return redirect(
        "user_order_detail",
        order_number=order.order_number,
    )
