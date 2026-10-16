from django.urls import path
from .views.adminside.product_list_view import product_list,product_variant
from .views.adminside.product_add_view import product_add
from .views.adminside.product_edit_view import product_edit
from .views.adminside.product_offer_view import product_offer,toggle_product_offer
from .views.userside.product_list_view import product_list as user_product_list
from .views.userside.product_details_view import product_details
from .views.adminside.product_delete_view import delete_product,restore_product
from products.views.adminside.inventory_view import (admin_inventory_list,admin_inventory_detail,admin_update_stock,)



urlpatterns = [
    path("admin_productslist/",product_list,name="admin_product_list"),
    path("admin_productsadd/",product_add,name="admin_product_add"),
    path("admin_productsedit/<int:product_id>/",product_edit,name="admin_product_edit",),
    path("admin_productoffer/<int:product_id>/", product_offer, name="admin_product_offer"),
    path("admin_productoffer_toggle/<int:offer_id>/",toggle_product_offer,name="admin_product_offer_toggle"),
    path("products/", user_product_list, name="user_product_list"),
    path("products/<int:product_id>/", product_details, name="user_product_details"),
    path("productvariant/<int:product_id>",product_variant,name="product_variant"),
    path("products/<int:product_id>/delete/",delete_product,name="delete_product"),
    path("products/<int:product_id>/restore/",restore_product,name="restore_product"),
    path("admin/inventory/", admin_inventory_list, name="admin_inventory_list"),
    path("admin/inventory/<int:product_id>/",admin_inventory_detail,name="admin_inventory_detail",),
    path("admin/inventory/variant/<int:variant_id>/update/",admin_update_stock,name="admin_update_stock", ),


]