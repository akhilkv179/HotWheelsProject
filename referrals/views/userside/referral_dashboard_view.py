from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render
from django.urls import reverse

from referrals.models import Referral, ReferralCode, ReferralOffer


def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


@login_required
def referral_dashboard(request):
    # The referral dashboard displays information through GET requests.
    if request.method != "GET":
        if wants_json(request):
            return JsonResponse(
                {"error": "Only GET requests are allowed."},
                status=405,
            )
        return HttpResponseNotAllowed(["GET"])

    #Get or create this customer's unique referral code and token.
    referral_profile, _ = ReferralCode.objects.get_or_create(
        user=request.user,
    )

    # Build a shareable signup URL containing the referral token.
    signup_path = reverse("signup")
    query_string = urlencode({
        "token": str(referral_profile.token),
    })
    referral_link = request.build_absolute_uri(
        f"{signup_path}?{query_string}"
    )

    # Retrieve referrals made by this customer.
    referrals = list(
        Referral.objects.filter(
            referrer=request.user,
        ).select_related(
            "referred_user",
            "referral_offer",
        ).order_by("-created_at")
    )

    # Use the latest configured offer as the current reward amount.
    current_offer = ReferralOffer.objects.order_by(
        "-created_at",
        "-pk",
    ).first()

    # Prepare referral history.
    referral_history = [
        {
            "username": referral.referred_user.username,
            "referral_code": referral.referral_code,
            "reward_amount": str(referral.reward_amount),
            "rewarded": referral.rewarded_at is not None,
            "rewarded_at": (
                referral.rewarded_at.isoformat()
                if referral.rewarded_at
                else None
            ),
            "created_at": referral.created_at.isoformat(),
        }
        for referral in referrals
    ]

    # Count all referrals.
    total_referrals = len(referrals)

    # Count referrals whose rewards have been recorded.
    successful_referrals = sum(
        1
        for referral in referrals
        if referral.rewarded_at is not None
    )

    # Calculate the total rewards earned from rewarded referrals.
    total_rewards_earned = sum(
        (
            referral.reward_amount
            for referral in referrals
            if referral.rewarded_at is not None
        ),
        start=0,
    )

    # Return referral information as JSON when requested.
    if wants_json(request):
        return JsonResponse(
            {
                "referral_code": referral_profile.code,
                "referral_link": referral_link,
                "reward_amount": (
                    str(current_offer.reward_amount)
                    if current_offer
                    else None
                ),
                "total_referrals": total_referrals,
                "successful_referrals": successful_referrals,
                "total_rewards_earned": str(total_rewards_earned),
                "referrals": referral_history,
            },
            status=200,
        )

    # Render the user-side referral dashboard.
    return render(
        request,
        "userside/referral_page.html",
        {
            "referral_profile": referral_profile,
            "referral_code": referral_profile.code,
            "referral_link": referral_link,
            "current_offer": current_offer,
            "referrals": referrals,
            "total_referrals": total_referrals,
            "successful_referrals": successful_referrals,
            "total_rewards_earned": total_rewards_earned,
        },
        status=200,
    )