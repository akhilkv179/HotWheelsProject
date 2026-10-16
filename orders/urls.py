
from django.urls import path

from .views.userside.checkout_view import checkout, order_success
from .views.userside.order_views import user_order_list, user_order_detail
from .views.userside.cancel_order_view import cancel_order
from .views.userside.return_order_view import request_return
from .views.userside.invoice_view import download_invoice
from .views.adminside.admin_order_views import (admin_order_list,admin_order_detail,admin_update_order_status,)
from orders.views.adminside.admin_return_views import (admin_return_list,admin_update_return_status,)

urlpatterns = [
    path("checkout/", checkout, name="checkout"),
    path("success/<str:order_number>/", order_success, name="order_success"),
    path("my-orders/", user_order_list, name="user_order_list"),
    path("my-orders/<str:order_number>/", user_order_detail, name="user_order_detail"),
    path("my-orders/<str:order_number>/items/<int:item_id>/cancel/",cancel_order,name="cancel_order",),
    path("my-orders/<str:order_number>/items/<int:item_id>/return/",request_return,name="request_return",),
    path("my-orders/<str:order_number>/invoice/", download_invoice, name="download_invoice"),
    path("admin/orders/", admin_order_list, name="admin_order_list"),
    path("admin/orders/<str:order_number>/", admin_order_detail, name="admin_order_detail"),
    path("admin/orders/<str:order_number>/status/",admin_update_order_status,name="admin_update_order_status",),
    path("admin/returns/", admin_return_list, name="admin_return_list"),
    path("admin/returns/<int:return_id>/status/",admin_update_return_status,name="admin_update_return_status",),
]