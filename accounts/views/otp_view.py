from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache

from ..models import User
from ..services.otp_service import generate_otp, get_otp_expiry
from ..services.email_service import send_otp_email


# Check whether the frontend expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Verify the signup OTP and create the customer's account.
@never_cache
def verify_otp(request):

    # Prevent an already logged-in customer from repeating signup.
    if request.user.is_authenticated:
        if wants_json(request):
            return JsonResponse({
                "success": True,
                "message": "You are already logged in.",
                "redirect_url": reverse("home"),
            }, status=200)

        return redirect("home")

    # Allow OTP verification only through GET and POST requests.
    if request.method not in ["GET", "POST"]:
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "Only GET and POST requests are allowed.",
            }, status=405)

        return HttpResponseNotAllowed(["GET", "POST"])

    if request.method == "POST":
        entered_otp = request.POST.get("otp", "").strip()

        stored_otp = request.session.get("signup_otp")
        stored_expiry = request.session.get("signup_otp_expiry")
        signup_data = request.session.get("signup_data")

        # Check whether the signup session still exists.
        if not stored_otp or not signup_data:
            if wants_json(request):
                return JsonResponse({
                    "success": False,
                    "message": "Signup session has expired.",
                    "redirect_url": reverse("signup"),
                }, status=410)

            messages.error(request, "Signup session has expired.")
            return redirect("signup")

        # Check whether the OTP expiry time exists.
        if not stored_expiry:
            if wants_json(request):
                return JsonResponse({
                    "success": False,
                    "message": "OTP has expired.",
                    "redirect_url": reverse("signup"),
                }, status=410)

            messages.error(request, "OTP has expired.")
            return redirect("signup")

        # Convert the stored expiry string into a datetime object.
        expiry_time = datetime.fromisoformat(stored_expiry)

        # Reject an OTP that has passed its expiry time.
        if timezone.now() > expiry_time:
            if wants_json(request):
                return JsonResponse({
                    "success": False,
                    "message": "OTP has expired. Please request a new OTP.",
                }, status=410)

            messages.error(
                request,
                "OTP has expired. Please request a new OTP."
            )
            return redirect("verify_otp")

        # Reject an empty OTP.
        if not entered_otp:
            if wants_json(request):
                return JsonResponse({
                    "success": False,
                    "message": "Please enter the OTP.",
                }, status=400)

            messages.error(request, "Please enter the OTP.")

        # Verify the OTP entered by the customer.
        elif entered_otp == stored_otp:

            # Create the customer account after successful verification.
            user = User(
                username=signup_data["username"],
                email=signup_data["email"],
                phone=signup_data["phone"],
                password=signup_data["password_hash"],
            )

            user.save()

            # Clear temporary signup data from the session.
            request.session.pop("signup_otp", None)
            request.session.pop("signup_otp_expiry", None)
            request.session.pop("last_otp_resend", None)
            request.session.pop("signup_data", None)

            if wants_json(request):
                return JsonResponse({
                    "success": True,
                    "message": "Account created successfully.",
                    "redirect_url": reverse("login"),
                }, status=201)

            messages.success(request, "Account created successfully.")
            return redirect("login")

        # Return an error when the OTP does not match.
        else:
            if wants_json(request):
                return JsonResponse({
                    "success": False,
                    "message": "Invalid OTP.",
                }, status=400)

            messages.error(request, "Invalid OTP.")

    # Calculate the remaining OTP validity time for the template.
    stored_expiry = request.session.get("signup_otp_expiry")
    remaining_seconds = 0

    if stored_expiry:
        expiry_time = datetime.fromisoformat(stored_expiry)
        remaining_seconds = max(
            0,
            int((expiry_time - timezone.now()).total_seconds())
        )

    # Display the existing OTP verification page.
    return render(
        request,
        "accounts/verify_otp.html",
        {"remaining_seconds": remaining_seconds},
    )


# Resend a signup OTP while enforcing the 30-second cooldown.
@never_cache
def resend_otp(request):

    # Allow OTP resend only through POST requests.
    if request.method != "POST":
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "Only POST requests are allowed.",
            }, status=405)

        return HttpResponseNotAllowed(["POST"])

    signup_data = request.session.get("signup_data")

    # Check whether the signup session still exists.
    if not signup_data:
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "Signup session has expired.",
                "redirect_url": reverse("signup"),
            }, status=410)

        messages.error(request, "Signup session has expired.")
        return redirect("signup")

    # Check when the last OTP was requested.
    last_resend = request.session.get("last_otp_resend")

    if last_resend:
        last_resend_time = datetime.fromisoformat(last_resend)
        time_passed = timezone.now() - last_resend_time

        # Enforce the 30-second resend cooldown.
        if time_passed < timedelta(seconds=30):
            retry_after = max(
                1,
                30 - int(time_passed.total_seconds())
            )

            if wants_json(request):
                response = JsonResponse({
                    "success": False,
                    "message": "Please wait before requesting another OTP.",
                    "retry_after": retry_after,
                }, status=429)
                response["Retry-After"] = str(retry_after)
                return response

            messages.error(
                request,
                "Please wait 30 seconds before requesting another OTP."
            )
            return redirect("verify_otp")

    # Record the time of this OTP request.
    request.session["last_otp_resend"] = timezone.now().isoformat()

    # Generate a new OTP and its expiry time.
    otp = generate_otp()
    otp_expiry = get_otp_expiry()

    request.session["signup_otp"] = otp
    request.session["signup_otp_expiry"] = otp_expiry.isoformat()

    # Send the new OTP to the email address used during signup.
    send_otp_email(signup_data["email"], otp)

    # Return success to a frontend expecting JSON.
    if wants_json(request):
        return JsonResponse({
            "success": True,
            "message": "A new OTP has been sent.",
            "remaining_seconds": max(
                0,
                int((otp_expiry - timezone.now()).total_seconds())
            ),
        }, status=200)

    messages.success(request, "A new OTP has been sent.")
    return redirect("verify_otp")