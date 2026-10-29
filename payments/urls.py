
from django.urls import path

from payments.views.razorpay_webhook_view import (
    razorpay_webhook_view,
)
from payments.views.userside.create_razorpay_order_view import (
    create_razorpay_order,
)
from payments.views.userside.verify_razorpay_payment_view import (
    verify_razorpay_payment_view,
)
from payments.views.userside.payment_failure_view import (
    record_razorpay_payment_failure,
)
# from payments.views.userside.expire_razorpay_payment_view import (
#     expire_razorpay_payment,
# )


urlpatterns = [
    path(
        "orders/<str:order_number>/create-order/",
        create_razorpay_order,
        name="create_razorpay_order",
    ),
    # path(
    #     "orders/<str:order_number>/expire-payment/",
    #     expire_razorpay_payment,
    #     name="expire_razorpay_payment",
    # ),
    path(
        "verify-razorpay-payment/",
        verify_razorpay_payment_view,
        name="verify_razorpay_payment",
    ),
    path(
        "payment-failure/",
        record_razorpay_payment_failure,
        name="record_razorpay_payment_failure",
    ),
    path(
        "razorpay-webhook/",
        razorpay_webhook_view,
        name="razorpay_webhook",
    ),
    path(
        "razorpay-webhook-v2/",
        razorpay_webhook_view,
        name="razorpay_webhook_v2",
    ),
]
