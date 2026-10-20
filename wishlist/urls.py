from django.urls import path

from .views.userside.wishlist_list_view import wishlist_list
from .views.userside.wishlist_add_view import wishlist_add

urlpatterns = [
    path("", wishlist_list, name="wishlist"),
    path("add/<int:variant_id>/", wishlist_add, name="wishlist_add"),

    
]