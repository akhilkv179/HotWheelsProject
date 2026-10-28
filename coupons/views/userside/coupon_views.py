from django.db.models import F
from django.shortcuts import render
from django.utils import timezone

from coupons.models import Coupon


def user_coupon_list(request):
    """
    Display coupons currently available to customers.
    """

    current_time = timezone.now()

    coupons = (
        Coupon.objects.filter(
            status__iexact="active",
            start_date__lte=current_time,
            expiry_date__gte=current_time,
            used_count__lt=F("usage_limit"),
        )
        .order_by("expiry_date", "code")
    )

    context = {
        "coupons": coupons,
    }

    return render(
        request,
        "userside/coupon_list.html",
        context,
    )