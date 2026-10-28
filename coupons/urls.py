
from django.urls import path

from coupons.views.userside.coupon_views import user_coupon_list
from coupons.views.adminside.coupon_views import (
    admin_coupon_list,
    admin_coupon_create,
    admin_coupon_delete,
    admin_coupon_toggle_status,
    admin_coupon_edit,
)

urlpatterns = [
    # Admin-side coupon URLs
    path("", admin_coupon_list, name="admin_coupon_list"),
    path("create/", admin_coupon_create, name="admin_coupon_create"),
    path("<int:coupon_id>/edit/", admin_coupon_edit, name="admin_coupon_edit"),
    path("<int:coupon_id>/delete/", admin_coupon_delete, name="admin_coupon_delete"),
    path(
        "<int:coupon_id>/toggle-status/",
        admin_coupon_toggle_status,
        name="admin_coupon_toggle_status",
    ),

    # User-side coupon URL
    path("user-coupon/", user_coupon_list, name="user_coupon_list"),
]
