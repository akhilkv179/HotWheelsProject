
import json
from decimal import Decimal

from django.test import RequestFactory, TestCase
from django.utils import timezone
from datetime import timedelta
from payments.models import Payment
from coupons.models import Coupon, CouponUsage
from accounts.models import Address, User
from cart.models import Cart, CartItem
from categories.models import Category
from orders.models import (
    Order,
    OrderItem,
    OrderStatusHistory,
    Return,
)
from orders.views.adminside.admin_order_views import (
    admin_update_order_status,
)
from orders.views.adminside.admin_return_views import (
    admin_update_return_status,
)
from orders.views.userside.cancel_order_view import cancel_order
from orders.views.userside.checkout_view import checkout
from payments.models import Refund
from products.models import Product, ProductVariant
from wallet.models import Wallet, WalletTransaction
from wallet.services.refund_service import credit_wallet_refund
from django.http import Http404
from orders.views.userside.order_views import (
    user_order_list,
    user_order_detail,
)
from orders.views.userside.return_order_view import request_return
from orders.views.userside.invoice_view import download_invoice








class WalletCheckoutAndRefundTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        self.user = User.objects.create_user(
            username="wallet_customer",
            email="wallet-customer@example.com",
            password="Test-password-123",
        )

        self.admin = User.objects.create_user(
            username="wallet_admin",
            email="wallet-admin@example.com",
            password="Test-password-123",
            is_staff=True,
        )

        self.address = Address.objects.create(
            user=self.user,
            full_name="Test Customer",
            phone="9876543210",
            address_line1="Test Street",
            address_line2="",
            landmark="Near Park",
            city="Tiruvalla",
            state="Kerala",
            postal_code="689101",
            address_type="home",
            is_default=True,
        )

        self.category = Category.objects.create(
            name="Test Cars",
            description="Test category",
            is_active=True,
            is_deleted=False,
        )

        self.product = Product.objects.create(
            category=self.category,
            name="Test Hot Wheels Car",
            description="Test product",
            low_stock_threshold=2,
            regular_price=Decimal("100.00"),
            is_active=True,
            is_deleted=False,
        )

        self.variant = ProductVariant.objects.create(
            product=self.product,
            color="Red",
            size="1:64",
            price=Decimal("100.00"),
            stock_quantity=10,
            is_active=True,
        )

        self.cart = Cart.objects.create(user=self.user)

        self.cart_item = CartItem.objects.create(
            cart=self.cart,
            product_variant=self.variant,
            quantity=1,
            unit_price=Decimal("100.00"),
        )

        self.wallet = Wallet.objects.create(
            user=self.user,
            balance=Decimal("200.00"),
            is_active=True,
        )

    def json_post(self, user, path, data):
        request = self.factory.post(
            path,
            data=data,
            HTTP_ACCEPT="application/json",
        )
        request.user = user
        return request

    def place_wallet_order(self):
        request = self.json_post(
            self.user,
            "/checkout/",
            {
                "payment_method": "wallet",
                "address_id": str(self.address.pk),
            },
        )

        response = checkout(request)

        self.assertEqual(
            response.status_code,
            201,
            response.content.decode(),
        )

        response_data = json.loads(response.content)

        return Order.objects.get(
            order_number=response_data["order_number"]
        )

    def create_return_for_refund(self):
        order = Order.objects.create(
            user=self.user,
            address=self.address,
            order_number="HW-TEST-RETURN-001",
            status="delivered",
            subtotal=Decimal("100.00"),
            discount_amount=Decimal("10.00"),
            shipping_amount=Decimal("50.00"),
            total_amount=Decimal("140.00"),
            delivery_method="Wallet",
        )

        item = OrderItem.objects.create(
            order=order,
            product_variant=self.variant,
            product_name=self.product.name,
            quantity=1,
            unit_price=Decimal("100.00"),
            total_price=Decimal("90.00"),
            discount_amount=Decimal("10.00"),
            item_status="returned",
        )

        return Return.objects.create(
            order_item=item,
            user=self.user,
            reason="Damaged product",
            description="The product arrived damaged.",
            user_add_note="Please refund the amount.",
            internal_note="",
            status="inspection_approved",
            requested_at=timezone.now(),
        )

    def test_wallet_checkout_deducts_balance_and_stock(self):
        order = self.place_wallet_order()

        self.wallet.refresh_from_db()
        self.variant.refresh_from_db()

        self.assertEqual(order.status, "confirmed")
        self.assertEqual(order.total_amount, Decimal("150.00"))
        self.assertEqual(self.wallet.balance, Decimal("50.00"))
        self.assertEqual(self.variant.stock_quantity, 9)
        self.assertFalse(self.cart.items.exists())

        self.assertTrue(
            order.payments.filter(
                payment_method="wallet",
                status="paid",
            ).exists()
        )

        self.assertTrue(
            WalletTransaction.objects.filter(
                wallet=self.wallet,
                transaction_type="debit",
                reference_id=order.order_number,
            ).exists()
        )

    def test_insufficient_wallet_balance_does_not_place_order(self):
        self.wallet.balance = Decimal("100.00")
        self.wallet.save(update_fields=["balance"])

        request = self.json_post(
            self.user,
            "/checkout/",
            {
                "payment_method": "wallet",
                "address_id": str(self.address.pk),
            },
        )

        response = checkout(request)
        response_data = json.loads(response.content)

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Insufficient wallet balance",
            response_data["error"],
        )

        self.wallet.refresh_from_db()
        self.variant.refresh_from_db()

        self.assertEqual(self.wallet.balance, Decimal("100.00"))
        self.assertEqual(self.variant.stock_quantity, 10)
        self.assertEqual(Order.objects.count(), 0)
        self.assertTrue(self.cart.items.exists())

    def test_cancelling_wallet_order_refunds_customer(self):
        order = self.place_wallet_order()
        item = order.items.get()

        request = self.json_post(
            self.user,
            f"/orders/{order.order_number}/cancel/{item.pk}/",
            {"reason": "Changed my mind"},
        )

        response = cancel_order(
            request,
            order_number=order.order_number,
            item_id=item.pk,
        )

        self.assertEqual(
            response.status_code,
            200,
            response.content.decode(),
        )

        order.refresh_from_db()
        self.wallet.refresh_from_db()
        self.variant.refresh_from_db()

        self.assertEqual(order.status, "cancelled")
        self.assertEqual(self.wallet.balance, Decimal("200.00"))
        self.assertEqual(self.variant.stock_quantity, 10)

        self.assertTrue(
            WalletTransaction.objects.filter(
                wallet=self.wallet,
                transaction_type="credit",
                reference_id=order.order_number,
            ).exists()
        )

    def test_approved_return_refunds_wallet(self):
        return_request = self.create_return_for_refund()

        request = self.json_post(
            self.admin,
            f"/admin/returns/{return_request.pk}/",
            {
                "status": "refund_processed",
                "internal_note": "Refund approved",
            },
        )

        response = admin_update_return_status(
            request,
            return_id=return_request.pk,
        )

        self.assertEqual(
            response.status_code,
            200,
            response.content.decode(),
        )

        self.wallet.refresh_from_db()
        return_request.refresh_from_db()

        self.assertEqual(self.wallet.balance, Decimal("290.00"))
        self.assertEqual(return_request.status, "refund_processed")

        refund = Refund.objects.get(return_request=return_request)

        self.assertEqual(refund.amount, Decimal("90.00"))
        self.assertEqual(refund.status, "processed")

    def test_existing_return_refund_is_not_credited_twice(self):
        return_request = self.create_return_for_refund()

        wallet_transaction = credit_wallet_refund(
            user=self.user,
            amount=Decimal("90.00"),
            transaction_id=f"RETURN-REFUND-{return_request.pk}",
            reference_id=f"RETURN-{return_request.pk}",
        )

        Refund.objects.create(
            return_request=return_request,
            wallet_transaction=wallet_transaction,
            amount=Decimal("90.00"),
            status="processed",
            processed_at=timezone.now(),
        )

        self.wallet.refresh_from_db()
        balance_before_retry = self.wallet.balance

        request = self.json_post(
            self.admin,
            f"/admin/returns/{return_request.pk}/",
            {
                "status": "refund_processed",
                "internal_note": "Retry",
            },
        )

        response = admin_update_return_status(
            request,
            return_id=return_request.pk,
        )

        self.wallet.refresh_from_db()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.wallet.balance, balance_before_retry)
        self.assertEqual(
            Refund.objects.filter(
                return_request=return_request
            ).count(),
            1,
        )

    def test_admin_cancellation_refunds_wallet_order_once(self):
        order = self.place_wallet_order()
        item = order.items.get()

        # The checkout has already deducted ₹150 from the wallet.
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal("50.00"))

        request = self.json_post(
            self.admin,
            f"/admin/orders/{order.order_number}/status/",
            {"status": "cancelled"},
        )

        response = admin_update_order_status(
            request,
            order_number=order.order_number,
        )

        self.assertEqual(
            response.status_code,
            200,
            response.content.decode(),
        )

        order.refresh_from_db()
        item.refresh_from_db()
        self.wallet.refresh_from_db()
        self.variant.refresh_from_db()

        self.assertEqual(order.status, "cancelled")
        self.assertEqual(item.item_status, "cancelled")
        self.assertEqual(self.wallet.balance, Decimal("200.00"))
        self.assertEqual(self.variant.stock_quantity, 10)

        refund_transactions = WalletTransaction.objects.filter(
            wallet=self.wallet,
            transaction_type="credit",
            transaction_id=f"ADMIN-CANCEL-{order.pk}",
            reference_id=order.order_number,
        )

        self.assertEqual(refund_transactions.count(), 1)

        # Retry the same status update; it must not credit the wallet again.
        retry_request = self.json_post(
            self.admin,
            f"/admin/orders/{order.order_number}/status/",
            {"status": "cancelled"},
        )

        retry_response = admin_update_order_status(
            retry_request,
            order_number=order.order_number,
        )

        self.assertEqual(retry_response.status_code, 200)

        self.wallet.refresh_from_db()

        self.assertEqual(self.wallet.balance, Decimal("200.00"))
        self.assertEqual(refund_transactions.count(), 1)



    def test_failed_checkout_does_not_consume_coupon(self):
        # Reduce the balance so it cannot cover the discounted order total.
        self.wallet.balance = Decimal("100.00")
        self.wallet.save(update_fields=["balance"])

        now = timezone.now()

        coupon = Coupon.objects.create(
            code="SAVE10",
            coupon_name="Save 10 Percent",
            discount_type="percentage",
            discount_value=Decimal("10.00"),
            minimum_spend=Decimal("100.00"),
            maximum_discount=500,
            usage_limit=10,
            used_count=0,
            start_date=now - timedelta(days=1),
            expiry_date=now + timedelta(days=7),
            status="active",
        )

        # The order costs ₹150 before the coupon.
        # The 10% coupon reduces it to ₹140, but the wallet has only ₹100.
        request = self.json_post(
            self.user,
            "/checkout/",
            {
                "payment_method": "wallet",
                "address_id": str(self.address.pk),
                "coupon_code": "SAVE10",
            },
        )

        response = checkout(request)

        self.assertEqual(response.status_code, 400)

        response_data = json.loads(response.content)
        self.assertIn(
            "Insufficient wallet balance",
            response_data["error"],
        )

        # The failed checkout must not consume the coupon.
        coupon.refresh_from_db()

        self.assertEqual(coupon.used_count, 0)
        self.assertEqual(
            CouponUsage.objects.filter(coupon=coupon).count(),
            0,
        )

        # Other checkout changes must also be rolled back.
        self.wallet.refresh_from_db()
        self.variant.refresh_from_db()

        self.assertEqual(self.wallet.balance, Decimal("100.00"))
        self.assertEqual(self.variant.stock_quantity, 10)
        self.assertTrue(self.cart.items.exists())
        self.assertEqual(Order.objects.count(), 0)



    def test_return_refund_subtracts_allocated_coupon_discount(self):
        now = timezone.now()

        # Create a coupon that gives 10% off the discounted subtotal.
        coupon = Coupon.objects.create(
            code="RETURN10",
            coupon_name="Return Test Coupon",
            discount_type="percentage",
            discount_value=Decimal("10.00"),
            minimum_spend=Decimal("100.00"),
            maximum_discount=500,
            usage_limit=10,
            used_count=1,
            start_date=now - timedelta(days=1),
            expiry_date=now + timedelta(days=7),
            status="active",
        )

        # The item costs ₹100, gets a ₹10 product offer,
        # and then receives a ₹9 coupon discount.
        order = Order.objects.create(
            user=self.user,
            address=self.address,
            coupon=coupon,
            order_number="HW-COUPON-RETURN-001",
            status="delivered",
            subtotal=Decimal("100.00"),
            discount_amount=Decimal("19.00"),
            shipping_amount=Decimal("50.00"),
            total_amount=Decimal("131.00"),
            delivery_method="Wallet",
        )

        item = OrderItem.objects.create(
            order=order,
            product_variant=self.variant,
            product_name=self.product.name,
            quantity=1,
            unit_price=Decimal("100.00"),
            total_price=Decimal("90.00"),
            discount_amount=Decimal("10.00"),
            item_status="returned",
        )

        CouponUsage.objects.create(
            coupon=coupon,
            order=order,
            user=self.user,
            discount_amount=Decimal("9.00"),
            used_at=now,
        )

        return_request = Return.objects.create(
            order_item=item,
            user=self.user,
            reason="Damaged product",
            description="The product arrived damaged.",
            user_add_note="Please refund the amount.",
            internal_note="",
            status="inspection_approved",
            requested_at=now,
        )

        request = self.json_post(
            self.admin,
            f"/admin/returns/{return_request.pk}/",
            {
                "status": "refund_processed",
                "internal_note": "Coupon-adjusted refund processed",
            },
        )

        response = admin_update_return_status(
            request,
            return_id=return_request.pk,
        )

        self.assertEqual(
            response.status_code,
            200,
            response.content.decode(),
        )

        # ₹90 after product offer minus ₹9 coupon discount = ₹81.
        refund = Refund.objects.get(return_request=return_request)

        self.assertEqual(refund.amount, Decimal("81.00"))
        self.assertEqual(refund.status, "processed")

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal("281.00"))



    def test_partial_cancellation_refunds_coupon_adjusted_amount(self):
        now = timezone.now()

        coupon = Coupon.objects.create(
            code="CANCEL10",
            coupon_name="Cancellation Test Coupon",
            discount_type="percentage",
            discount_value=Decimal("10.00"),
            minimum_spend=Decimal("100.00"),
            maximum_discount=500,
            usage_limit=10,
            used_count=1,
            start_date=now - timedelta(days=1),
            expiry_date=now + timedelta(days=7),
            status="active",
        )

        # Two items cost ₹200 before discounts.
        # Product offers reduce the subtotal to ₹180.
        # The 10% coupon saves another ₹18.
        # Shipping is ₹50, so the original total is ₹212.
        order = Order.objects.create(
            user=self.user,
            address=self.address,
            coupon=coupon,
            order_number="HW-COUPON-CANCEL-001",
            status="confirmed",
            subtotal=Decimal("200.00"),
            discount_amount=Decimal("38.00"),
            shipping_amount=Decimal("50.00"),
            total_amount=Decimal("212.00"),
            delivery_method="Wallet",
        )

        first_item = OrderItem.objects.create(
            order=order,
            product_variant=self.variant,
            product_name=self.product.name,
            quantity=1,
            unit_price=Decimal("100.00"),
            total_price=Decimal("90.00"),
            discount_amount=Decimal("10.00"),
            item_status="active",
        )

        remaining_item = OrderItem.objects.create(
            order=order,
            product_variant=self.variant,
            product_name=self.product.name,
            quantity=1,
            unit_price=Decimal("100.00"),
            total_price=Decimal("90.00"),
            discount_amount=Decimal("10.00"),
            item_status="active",
        )

        CouponUsage.objects.create(
            coupon=coupon,
            order=order,
            user=self.user,
            discount_amount=Decimal("18.00"),
            used_at=now,
        )

        # Represent stock after the original two-item purchase.
        self.variant.stock_quantity = 8
        self.variant.save(update_fields=["stock_quantity"])

        # Represent the already-paid wallet order.
        self.wallet.balance = Decimal("0.00")
        self.wallet.save(update_fields=["balance"])

        Payment.objects.create(
            order=order,
            amount=Decimal("212.00"),
            payment_method="wallet",
            status="paid",
            transaction_id="TEST-COUPON-CANCEL-PAYMENT",
            paid_at=now,
        )

        request = self.json_post(
            self.user,
            f"/orders/{order.order_number}/cancel/{first_item.pk}/",
            {"reason": "Changed my mind"},
        )

        response = cancel_order(
            request,
            order_number=order.order_number,
            item_id=first_item.pk,
        )

        self.assertEqual(
            response.status_code,
            200,
            response.content.decode(),
        )

        order.refresh_from_db()
        first_item.refresh_from_db()
        remaining_item.refresh_from_db()
        self.wallet.refresh_from_db()
        self.variant.refresh_from_db()

        # The cancelled item receives a refund of ₹90 minus its ₹9 coupon share.
        self.assertEqual(self.wallet.balance, Decimal("81.00"))

        # The remaining item retains its ₹10 product discount and ₹9 coupon share.
        self.assertEqual(order.subtotal, Decimal("100.00"))
        self.assertEqual(order.discount_amount, Decimal("19.00"))
        self.assertEqual(order.total_amount, Decimal("131.00"))

        self.assertEqual(first_item.item_status, "cancelled")
        self.assertEqual(remaining_item.item_status, "active")
        self.assertEqual(self.variant.stock_quantity, 9)

        # Ensure the stable cancellation transaction was recorded once.
        self.assertEqual(
            WalletTransaction.objects.filter(
                wallet=self.wallet,
                transaction_id=f"CANCEL-{order.pk}-{first_item.pk}",
            ).count(),
            1,
        )



    def test_wallet_checkout_applies_coupon_correctly(self):
        now = timezone.now()

        coupon = Coupon.objects.create(
            code="CHECKOUT10",
            coupon_name="Checkout 10 Percent",
            discount_type="percentage",
            discount_value=Decimal("10.00"),
            minimum_spend=Decimal("100.00"),
            maximum_discount=500,
            usage_limit=10,
            used_count=0,
            start_date=now - timedelta(days=1),
            expiry_date=now + timedelta(days=7),
            status="active",
        )

        # Cart subtotal: ₹100
        # Coupon discount: ₹10
        # Shipping: ₹50
        # Final payment: ₹140
        request = self.json_post(
            self.user,
            "/checkout/",
            {
                "payment_method": "wallet",
                "address_id": str(self.address.pk),
                "coupon_code": "CHECKOUT10",
            },
        )

        response = checkout(request)

        self.assertEqual(
            response.status_code,
            201,
            response.content.decode(),
        )

        data = json.loads(response.content)
        order = Order.objects.get(
            order_number=data["order_number"]
        )

        self.wallet.refresh_from_db()
        self.variant.refresh_from_db()
        coupon.refresh_from_db()

        self.assertEqual(order.coupon_id, coupon.pk)
        self.assertEqual(order.discount_amount, Decimal("10.00"))
        self.assertEqual(order.total_amount, Decimal("140.00"))
        self.assertEqual(self.wallet.balance, Decimal("60.00"))
        self.assertEqual(self.variant.stock_quantity, 9)

        self.assertEqual(coupon.used_count, 1)
        self.assertEqual(
            CouponUsage.objects.filter(
                coupon=coupon,
                order=order,
                user=self.user,
            ).count(),
            1,
        )

        self.assertFalse(self.cart.items.exists())




class OrderHistoryAndReturnViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        self.user = User.objects.create_user(
            username="history_customer",
            email="history-customer@example.com",
            password="Test-password-123",
        )

        self.other_user = User.objects.create_user(
            username="other_history_customer",
            email="other-history@example.com",
            password="Test-password-123",
        )

        self.address = Address.objects.create(
            user=self.user,
            full_name="History Customer",
            phone="9876543210",
            address_line1="Test Street",
            address_line2="",
            landmark="Near Park",
            city="Tiruvalla",
            state="Kerala",
            postal_code="689101",
            address_type="home",
            is_default=True,
        )

        self.category = Category.objects.create(
            name="History Test Cars",
            description="Test category",
            is_active=True,
            is_deleted=False,
        )

        self.product = Product.objects.create(
            category=self.category,
            name="History Test Car",
            description="Test product",
            low_stock_threshold=2,
            regular_price=Decimal("100.00"),
            is_active=True,
            is_deleted=False,
        )

        self.variant = ProductVariant.objects.create(
            product=self.product,
            color="Red",
            size="1:64",
            price=Decimal("100.00"),
            stock_quantity=10,
            is_active=True,
        )

        self.order = self.create_order(
            self.user,
            "HW-HISTORY-001",
        )

    def create_order(self, user, order_number, status="pending"):
        return Order.objects.create(
            user=user,
            address=self.address,
            order_number=order_number,
            status=status,
            subtotal=Decimal("100.00"),
            discount_amount=Decimal("0.00"),
            shipping_amount=Decimal("50.00"),
            total_amount=Decimal("150.00"),
            delivery_method="Cash on Delivery",
        )

    def json_get(self, user, path, data=None):
        request = self.factory.get(
            path,
            data=data or {},
            HTTP_ACCEPT="application/json",
        )
        request.user = user
        return request

    def json_post(self, user, path, data):
        request = self.factory.post(
            path,
            data=data,
            HTTP_ACCEPT="application/json",
        )
        request.user = user
        return request

    def test_order_list_shows_only_logged_in_users_orders(self):
        self.create_order(self.user, "HW-HISTORY-002")
        self.create_order(
            self.other_user,
            "HW-HISTORY-OTHER",
        )

        request = self.json_get(self.user, "/orders/")
        response = user_order_list(request)

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        numbers = [
            order["order_number"]
            for order in data["orders"]
        ]

        self.assertIn("HW-HISTORY-001", numbers)
        self.assertIn("HW-HISTORY-002", numbers)
        self.assertNotIn("HW-HISTORY-OTHER", numbers)
        self.assertEqual(data["pagination"]["total_orders"], 2)

    def test_order_list_search_filters_by_order_number(self):
        self.create_order(self.user, "HW-HISTORY-SEARCH")

        request = self.json_get(
            self.user,
            "/orders/",
            {"search": "SEARCH"},
        )
        response = user_order_list(request)

        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)

        self.assertEqual(data["pagination"]["total_orders"], 1)
        self.assertEqual(
            data["orders"][0]["order_number"],
            "HW-HISTORY-SEARCH",
        )

    def test_customer_cannot_view_another_users_order(self):
        other_order = self.create_order(
            self.other_user,
            "HW-HISTORY-PRIVATE",
        )

        request = self.json_get(
            self.user,
            f"/orders/{other_order.order_number}/",
        )

        with self.assertRaises(Http404):
            user_order_detail(
                request,
                order_number=other_order.order_number,
            )

    def test_return_is_rejected_before_delivery(self):
        item = OrderItem.objects.create(
            order=self.order,
            product_variant=self.variant,
            product_name=self.product.name,
            quantity=1,
            unit_price=Decimal("100.00"),
            total_price=Decimal("100.00"),
            discount_amount=Decimal("0.00"),
            item_status="active",
        )

        request = self.json_post(
            self.user,
            "/orders/return/",
            {
                "reason": "Damaged",
                "description": "The package was damaged.",
            },
        )

        response = request_return(
            request,
            order_number=self.order.order_number,
            item_id=item.pk,
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            Return.objects.filter(order_item=item).exists()
        )

    def test_delivered_item_can_be_returned_only_once(self):
        self.order.status = "delivered"
        self.order.save(update_fields=["status", "updated_at"])

        item = OrderItem.objects.create(
            order=self.order,
            product_variant=self.variant,
            product_name=self.product.name,
            quantity=1,
            unit_price=Decimal("100.00"),
            total_price=Decimal("100.00"),
            discount_amount=Decimal("0.00"),
            item_status="active",
        )

        payload = {
            "reason": "Damaged",
            "description": "The product arrived damaged.",
            "user_add_note": "Please inspect it.",
        }

        first_response = request_return(
            self.json_post(
                self.user,
                "/orders/return/",
                payload,
            ),
            order_number=self.order.order_number,
            item_id=item.pk,
        )

        second_response = request_return(
            self.json_post(
                self.user,
                "/orders/return/",
                payload,
            ),
            order_number=self.order.order_number,
            item_id=item.pk,
        )

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 400)
        self.assertEqual(
            Return.objects.filter(order_item=item).count(),
            1,
        )

    def test_invoice_is_generated_for_the_order_owner(self):
        request = self.factory.get(
            f"/orders/{self.order.order_number}/invoice/",
        )
        request.user = self.user

        response = download_invoice(
            request,
            order_number=self.order.order_number,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_customer_cannot_download_another_users_invoice(self):
        other_order = self.create_order(
            self.other_user,
            "HW-HISTORY-PRIVATE-INVOICE",
        )

        request = self.factory.get(
            f"/orders/{other_order.order_number}/invoice/",
        )
        request.user = self.user

        with self.assertRaises(Http404):
            download_invoice(
                request,
                order_number=other_order.order_number,
            )
