from django.urls import path
from . import views


urlpatterns = [
    path('login/',views.admin_login,name='admin_login'),
    path("dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("users/", views.user_list, name="user_list"),
    path("users/<int:user_id>/toggle-status/", views.toggle_user_status, name="toggle_user_status"),
    

    
]
