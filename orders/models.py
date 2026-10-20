from django.db import models

from accounts.models import User, Address
from products.models import ProductVariant
from coupons.models import Coupon


class Order(models.Model):
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name="orders")
    address = models.ForeignKey(Address,on_delete=models.SET_NULL,null=True,related_name="orders")
    coupon = models.ForeignKey(Coupon,on_delete=models.SET_NULL,null=True,blank=True,related_name="orders")
    order_number = models.CharField(max_length=255)
    status = models.CharField(max_length=100)
    subtotal = models.DecimalField(max_digits=10,decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10,decimal_places=2)
    shipping_amount = models.DecimalField(max_digits=10,decimal_places=2)
    total_amount = models.DecimalField(max_digits=10,decimal_places=2)
    delivery_method = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.order_number


class OrderItem(models.Model):
    ITEM_STATUS_CHOICES = [
        ("active", "Active"),
        ("cancelled", "Cancelled"),
        ("returned", "Returned"),
    ]

    order = models.ForeignKey( Order,on_delete=models.CASCADE,related_name="items")
    product_variant = models.ForeignKey(ProductVariant,on_delete=models.CASCADE,related_name="order_items")
    product_name = models.CharField(max_length=255)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=10,decimal_places=2)
    total_price = models.DecimalField(max_digits=10,decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10,decimal_places=2)
    item_status = models.CharField(max_length=20,choices=ITEM_STATUS_CHOICES,default="active")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.order.order_number} - {self.product_name}"


class OrderAddress(models.Model):
    order = models.OneToOneField(Order,on_delete=models.CASCADE,related_name="order_address")
    address_label = models.CharField(max_length=255)
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255,blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    pin = models.CharField(max_length=20)
    custom_label = models.CharField(max_length=255,blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.order.order_number} - {self.full_name}"


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order,on_delete=models.CASCADE,related_name="status_history")
    status = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.order.order_number} - {self.status}"


class Return(models.Model):
    order_item = models.ForeignKey(OrderItem,on_delete=models.CASCADE,related_name="returns")
    user = models.ForeignKey(User,on_delete=models.CASCADE,related_name="returns")
    reason = models.CharField(max_length=255)
    description = models.TextField()
    user_add_note = models.TextField()
    internal_note = models.TextField()
    status = models.CharField(max_length=100)
    requested_at = models.DateTimeField()
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Return - {self.order_item.product_name}"
