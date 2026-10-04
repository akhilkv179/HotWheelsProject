from django.urls import path

from .views.userside.wishlist_list_view import wishlist_list
from .views.userside.wishlist_remove_view import wishlist_remove
from .views.userside.wishlist_add_view import wishlist_add

urlpatterns = [
    path("", wishlist_list, name="wishlist"),
    path("remove/<int:item_id>/", wishlist_remove, name="wishlist_remove"),
    path("add/<int:variant_id>/", wishlist_add, name="wishlist_add"),

    
]