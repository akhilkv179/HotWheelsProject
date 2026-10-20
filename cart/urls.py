from django.urls import path
from .views.userside.add_to_cart_view import add_to_cart
from .views.userside.remove_from_cart_view import remove_from_cart
from .views.userside.cart_list_view import cart_list
from .views.userside.update_cart_quantity_view import update_cart_quantity
from .views.userside.checkout_view import checkout

urlpatterns = [
    path("add/<int:variant_id>/", add_to_cart, name="add_to_cart"),
    path("remove/<int:item_id>/", remove_from_cart, name="remove_from_cart"),
    path("",cart_list, name="cart_list"),
    path("update/<int:item_id>/<str:action>/",update_cart_quantity,name="update_cart_quantity"),
    path("checkout/", checkout, name="checkout"),


]