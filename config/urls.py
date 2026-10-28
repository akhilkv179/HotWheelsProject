
"""
URL configuration for config project.

The `urlpatterns` list routes URLs for the project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("d/", include("admin_panel.urls")),
    path("d/coupons/", include("coupons.urls")),
    path("", include("accounts.urls")),
    path("p/", include("products.urls")),
    path("cart/", include("cart.urls")),
    path("c/", include("categories.urls")),
    path("w/", include("wishlist.urls")),
    path("orders/", include("orders.urls")),
    path("payments/", include("payments.urls")),
    path("wallet/", include("wallet.urls")),
    path("referrals/", include("referrals.urls")),
    path("reviews/", include("reviews.urls")),
    path("coupons/", include("coupons.urls")),

]

urlpatterns += static(
    settings.MEDIA_URL,
    document_root=settings.MEDIA_ROOT,
)
