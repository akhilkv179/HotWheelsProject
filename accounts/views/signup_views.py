import uuid

from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache

from ..forms import SignupForm
from ..services.otp_service import generate_otp, get_otp_expiry
from ..services.email_service import send_otp_email

from referrals.models import ReferralCode


def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


def resolve_referral(code="", token=""):
    code = code.strip()
    token = token.strip()

    # Resolve referral using a referral code.
    if code:
        referral = (
            ReferralCode.objects.select_related("user")
            .filter(code__iexact=code)
            .first()
        )

        if referral:
            return referral, None

        return None, "Invalid referral code."

    # Resolve referral using a token URL.
    if token:
        try:
            token_value = uuid.UUID(token)
        except (ValueError, AttributeError, TypeError):
            return None, "Invalid referral link."

        referral = (
            ReferralCode.objects.select_related("user")
            .filter(token=token_value)
            .first()
        )

        if referral:
            return referral, None

        return None, "Invalid referral link."

    return None, None


@never_cache
def signup(request):
    if request.user.is_authenticated:
        if wants_json(request):
            return JsonResponse(
                {
                    "success": True,
                    "message": "You are already logged in.",
                    "redirect_url": reverse("home"),
                },
                status=200,
            )

        return redirect("home")

    if request.method not in ["GET", "POST"]:
        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Only GET and POST requests are allowed.",
                },
                status=405,
            )

        return HttpResponseNotAllowed(["GET", "POST"])

    # --------------------------------------------------
    # GET: Handle referral links and referral codes.
    # --------------------------------------------------
    if request.method == "GET":
        referral_code = (
            request.GET.get("ref", "").strip()
            or request.GET.get("referral_code", "").strip()
        )

        referral_token = (
            request.GET.get("token", "").strip()
            or request.GET.get("referral_token", "").strip()
        )

        if referral_code or referral_token:
            referral, error = resolve_referral(
                code=referral_code,
                token=referral_token,
            )

            if referral:
                request.session["signup_referral_code"] = referral.code
            else:
                request.session.pop("signup_referral_code", None)

                messages.error(
                    request,
                    error or "Invalid referral information.",
                )

        elif not request.session.get("signup_data"):
            request.session.pop("signup_referral_code", None)

    # --------------------------------------------------
    # POST: Validate signup and process referral details.
    # --------------------------------------------------
    if request.method == "POST":
        form = SignupForm(request.POST)

        if form.is_valid():
            data = form.cleaned_data

            # A manually entered code takes priority.
            referral_code = request.POST.get(
                "referral_code", ""
            ).strip()

            # Also support referral codes and tokens supplied
            # through URL query parameters.
            referral_code = (
                referral_code
                or request.GET.get("ref", "").strip()
                or request.GET.get("referral_code", "").strip()
            )

            referral_token = (
                request.POST.get("referral_token", "").strip()
                or request.GET.get("token", "").strip()
                or request.GET.get("referral_token", "").strip()
            )

            # Validate a newly supplied code or token.
            if referral_code or referral_token:
                referral, error = resolve_referral(
                    code=referral_code,
                    token=referral_token,
                )

                if not referral:
                    request.session.pop(
                        "signup_referral_code", None
                    )

                    error_message = (
                        error or "Invalid referral information."
                    )

                    if wants_json(request):
                        return JsonResponse(
                            {
                                "success": False,
                                "message": error_message,
                            },
                            status=400,
                        )

                    messages.error(request, error_message)

                    return render(
                        request,
                        "accounts/signup.html",
                        {
                            "form": form,
                            "username": data["username"],
                            "email": data["email"],
                            "phone": data["phone"],
                            "referral_code": request.POST.get(
                                "referral_code", ""
                            ),
                        },
                        status=400,
                    )

                request.session["signup_referral_code"] = (
                    referral.code
                )

            # If no new referral information was supplied,
            # retain a valid referral already captured from
            # the referral URL in the session.

            password_hash = make_password(data["password"])

            request.session["signup_data"] = {
                "username": data["username"],
                "email": data["email"],
                "phone": data["phone"],
                "password_hash": password_hash,
            }

            otp = generate_otp()
            otp_expiry = get_otp_expiry()

            request.session["signup_otp"] = otp
            request.session["signup_otp_expiry"] = (
                otp_expiry.isoformat()
            )

            send_otp_email(data["email"], otp)

            if wants_json(request):
                return JsonResponse(
                    {
                        "success": True,
                        "message": (
                            "OTP has been sent to your email address."
                        ),
                        "redirect_url": reverse("verify_otp"),
                    },
                    status=202,
                )

            messages.success(
                request,
                "OTP has been sent to your email address.",
            )

            return redirect("verify_otp")

        # Signup form validation failed.
        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Please correct the signup form errors.",
                    "errors": form.errors.get_json_data(),
                },
                status=400,
            )

        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)

    else:
        form = SignupForm()

    context = {
        "form": form,
        "username": request.POST.get("username", ""),
        "email": request.POST.get("email", ""),
        "phone": request.POST.get("phone", ""),
        "referral_code": request.POST.get(
            "referral_code",
            request.session.get("signup_referral_code", ""),
        ),
    }

    return render(
        request,
        "accounts/signup.html",
        context,
        status=200,
    )
