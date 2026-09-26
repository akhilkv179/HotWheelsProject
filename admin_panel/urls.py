from django.urls import path
from .views.admin_login_view import admin_login
from .views.admin_dashboard_view import admin_dashboard
from .views.user_list_view import user_list
from .views.toggle_user_status_view import toggle_user_status
from .views.admin_forgot_password_view import admin_forgot_password
from .views.admin_verify_forgot_password_otp_view import admin_verify_forgot_password_otp
from .views.admin_set_new_password_view import admin_set_new_password


urlpatterns = [
    path("admin_login/", admin_login, name="admin_login"),
    path("dashboard/",admin_dashboard, name="admin_dashboard"),
    path("users/",user_list, name="user_list"),
    path("users/<int:user_id>/toggle-status/", toggle_user_status, name="toggle_user_status"),
    path("forgot-password/",admin_forgot_password,name="admin_forgot_password"),
    path("forgot-password/verify-otp/",admin_verify_forgot_password_otp,name="admin_verify_forgot_password_otp",),
    path("forgot-password/set-new-password/",admin_set_new_password,name="admin_set_new_password",),
    
]
