
from django.urls import path

from referrals.views.userside.referral_dashboard_view import (
    referral_dashboard,
)
from referrals.views.adminside.referral_offer_views import (
    admin_referral_offer_list,
    admin_referral_offer_create,
)


urlpatterns = [
    # Customer referral dashboard
    path(
        "",
        referral_dashboard,
        name="referral_dashboard",
    ),

    # Admin referral offer management
    path(
        "admin/offers/",
        admin_referral_offer_list,
        name="admin_referral_offer_list",
    ),
    path(
        "admin/offers/create/",
        admin_referral_offer_create,
        name="admin_referral_offer_create",
    ),
]
