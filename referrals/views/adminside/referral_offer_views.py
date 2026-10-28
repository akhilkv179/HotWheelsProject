from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import redirect, render

from admin_panel.decorators import admin_required
from referrals.models import Referral, ReferralOffer


LIST_TEMPLATE = "adminside/admin_referral_offer_list.html"
FORM_TEMPLATE = "adminside/admin_referral_offer_form.html"


def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


def serialize_offer(offer):
    return {
        "id": offer.pk,
        "reward_amount": str(offer.reward_amount),
        "created_at": offer.created_at.isoformat(),
    }


def serialize_referral(referral):
    return {
        "referral_id": referral.pk,
        "referrer": referral.referrer.username,
        "referred_customer": referral.referred_user.username,
        "referral_code": referral.referral_code,
        "joined_date": (
            referral.referred_user.date_joined.isoformat()
            if referral.referred_user.date_joined
            else None
        ),
        "reward_amount": str(referral.reward_amount),
        "rewarded": referral.rewarded_at is not None,
    }


# Display referral offers and referral records with pagination.
@admin_required
def admin_referral_offer_list(request):
    if request.method != "GET":
        if wants_json(request):
            return JsonResponse(
                {"error": "Only GET requests are allowed."},
                status=405,
            )
        return HttpResponseNotAllowed(["GET"])

    # Retrieve referral reward offers.
    offers = ReferralOffer.objects.order_by(
        "-created_at",
        "-pk",
    )

    paginator = Paginator(offers, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    # Retrieve referral records with related customer information.
    referral_records = Referral.objects.select_related(
        "referrer",
        "referred_user",
        "referral_offer",
    ).order_by("-created_at", "-pk")

    referral_paginator = Paginator(referral_records, 10)
    referral_page_obj = referral_paginator.get_page(
        request.GET.get("referral_page")
    )

    if wants_json(request):
        return JsonResponse(
            {
                "offers": [
                    serialize_offer(offer)
                    for offer in page_obj.object_list
                ],
                "pagination": {
                    "current_page": page_obj.number,
                    "total_pages": paginator.num_pages,
                    "total_offers": paginator.count,
                    "has_previous": page_obj.has_previous(),
                    "has_next": page_obj.has_next(),
                },
                "referrals": [
                    serialize_referral(referral)
                    for referral in referral_page_obj.object_list
                ],
                "referral_pagination": {
                    "current_page": referral_page_obj.number,
                    "total_pages": referral_paginator.num_pages,
                    "total_referrals": referral_paginator.count,
                    "has_previous": referral_page_obj.has_previous(),
                    "has_next": referral_page_obj.has_next(),
                },
            },
            status=200,
        )

    return render(
        request,
        LIST_TEMPLATE,
        {
            "offers": page_obj,
            "page_obj": page_obj,
            "referrals": referral_page_obj,
            "referral_page_obj": referral_page_obj,
        },
        status=200,
    )


# Create a referral reward offer.
@admin_required
def admin_referral_offer_create(request):
    if request.method not in ("GET", "POST"):
        if wants_json(request):
            return JsonResponse(
                {"error": "Only GET and POST requests are allowed."},
                status=405,
            )
        return HttpResponseNotAllowed(["GET", "POST"])

    if request.method == "GET":
        if wants_json(request):
            return JsonResponse(
                {
                    "message": "Submit reward_amount to create an offer.",
                    "fields": ["reward_amount"],
                },
                status=200,
            )

        return render(
            request,
            FORM_TEMPLATE,
            {"reward_amount": ""},
        )

    raw_amount = request.POST.get("reward_amount", "").strip()

    if not raw_amount:
        error_message = "Reward amount is required."
        amount = None
    else:
        try:
            amount = Decimal(raw_amount)
        except (InvalidOperation, ValueError):
            amount = None

        if amount is None:
            error_message = "Enter a valid reward amount."
        elif not amount.is_finite():
            error_message = "Enter a valid reward amount."
        elif amount <= Decimal("0.00"):
            error_message = "Reward amount must be greater than zero."
        elif amount != amount.quantize(Decimal("0.01")):
            error_message = (
                "Reward amount can have at most two decimal places."
            )
        elif amount > Decimal("99999999.99"):
            error_message = "Reward amount exceeds the permitted maximum."
        else:
            error_message = None

    if error_message:
        if wants_json(request):
            return JsonResponse(
                {"error": error_message},
                status=400,
            )

        messages.error(request, error_message)
        return render(
            request,
            FORM_TEMPLATE,
            {"reward_amount": raw_amount},
            status=400,
        )

    offer = ReferralOffer.objects.create(
        reward_amount=amount,
    )

    if wants_json(request):
        return JsonResponse(
            {
                "message": "Referral reward offer created successfully.",
                "offer": serialize_offer(offer),
            },
            status=201,
        )

    messages.success(
        request,
        "Referral reward offer created successfully.",
    )
    return redirect("admin_referral_offer_list")