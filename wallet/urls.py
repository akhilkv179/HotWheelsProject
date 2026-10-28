
from django.urls import path

from wallet.views.userside.wallet_view import wallet_view
from wallet.views.userside.add_funds_view import (
    create_wallet_topup_order,
    verify_wallet_topup_payment,
)


urlpatterns = [
    path("", wallet_view, name="wallet"),
    path(
        "add-funds/create-order/",
        create_wallet_topup_order,
        name="create_wallet_topup_order",
    ),
    path(
        "add-funds/verify-payment/",
        verify_wallet_topup_payment,
        name="verify_wallet_topup_payment",
    ),
]
