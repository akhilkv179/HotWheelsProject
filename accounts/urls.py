from django.urls import path
from .views.signup_views import signup
from .views.otp_view import verify_otp,resend_otp
from .views.google_auth_views import google_login,google_callback
from .views.login_views import login_view
from .views.password_reset_views import (verify_reset_otp,reset_password,)
from .views.forgot_password_views import forgot_password
from .views.profile_view import profile_view
from .views.edit_profile_view import edit_profile
from .views.email_change_views import verify_email_change_otp
from .views.profile_change_password import (change_password,verify_password_change_otp,set_new_password)
from .views.profile_image import change_profile_image
from .views.add_address_view import add_address
from .views.address_list_view import address_list
from .views.edit_address_view import edit_address
from .views.delete_address_view import delete_address
from .views.logout_view import logout_view
from .views.home_view import home_view


urlpatterns = [
    path("signup/", signup, name="signup"),
    path("verify-otp/",verify_otp, name="verify_otp"),
    path("resend-otp/", resend_otp, name="resend_otp"),
    path("google/", google_login, name="google_login"),
    path("google/callback/",google_callback,name="google_callback"),
    path("login/", login_view, name="login"),
    path("forgot-password/",forgot_password,name="forgot_password"),
    path("verify-reset-otp/",verify_reset_otp,name="verify_reset_otp"),
    path("reset-password/",reset_password,name="reset_password"),
    path("profile/", profile_view, name="profile"),
    path("profile/edit/",edit_profile, name="edit_profile"),
    path("verify-email-change-otp/",verify_email_change_otp,name="verify_email_change_otp"),
    path("verify-password-change-otp/",verify_password_change_otp, name="verify_password_change_otp"),
    path("change-password/",change_password,name="change_password"),
    path("set-new-password/",set_new_password,name="set_new_password"),
    path("profile/change-image/",change_profile_image,name="change_profile_image"),
    path("addresses/add/",add_address,name="add_address"),
    path("addresses/",address_list,name="address_list"),
    path("addresses/<int:address_id>/edit/",edit_address,name="edit_address"),
    path("addresses/<int:address_id>/delete/",delete_address,name="delete_address"),
    path("logout/",logout_view,name="logout"),
    path("home/",home_view,name="home"),
    

    
]