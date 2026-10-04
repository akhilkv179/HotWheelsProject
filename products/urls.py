from django.urls import path
from .views.adminside.product_list_view import product_list
from .views.adminside.product_add_view import product_add
from .views.adminside.product_edit_view import product_edit
from .views.adminside.product_offer_view import product_offer,toggle_product_offer
from .views.userside.product_list_view import product_list as user_product_list
from .views.userside.product_details_view import product_details

urlpatterns = [
    path("admin_productslist/",product_list,name="admin_product_list"),
    path("admin_productsadd/",product_add,name="admin_product_add"),
    path("admin_productsedit/<int:product_id>/",product_edit,name="admin_product_edit",),
    path("admin_productoffer/<int:product_id>/", product_offer, name="admin_product_offer"),
    path("admin_productoffer_toggle/<int:offer_id>/",toggle_product_offer,name="admin_product_offer_toggle"),
    path("products/", user_product_list, name="user_product_list"),
    path("products/<int:product_id>/", product_details, name="user_product_details"),

]