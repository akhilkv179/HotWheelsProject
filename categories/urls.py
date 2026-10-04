from django.urls import path
from .views.adminside.category_list_view import category_list
from .views.adminside.category_add_view import category_add
from .views.adminside.category_edit_view import category_edit
from .views.adminside.category_delete_view import category_delete
from .views.adminside.category_offer_view import category_offer, toggle_category_offer
from .views.adminside.category_offer_edit_view import category_offer_edit





urlpatterns = [
    path("admin_categories/",category_list,name="admin_category_list"),
    path("admin_categories/add/",category_add,name="admin_category_add"),
    path("admin_categories/edit/<int:category_id>/",category_edit,name="admin_category_edit"),
    path("admin_categories/delete/<int:category_id>/",category_delete,name="admin_category_delete"),
    path("admin_categoryoffer/<int:category_id>/",category_offer,name="admin_category_offer"),
    path("admin_categoryoffer_toggle/<int:offer_id>/",toggle_category_offer,name="admin_category_offer_toggle"),
    path("admin_categoryoffer/edit/<int:offer_id>/",category_offer_edit,name="admin_category_offer_edit"),
]