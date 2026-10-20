from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache

from ..forms import SignupForm
from ..services.otp_service import generate_otp, get_otp_expiry
from ..services.email_service import send_otp_email


# Check whether the frontend expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Register a new user account and initiate email OTP verification.
@never_cache
def signup(request):

    # Redirect already authenticated users to the home page.
    if request.user.is_authenticated:
        if wants_json(request):
            return JsonResponse({
                "success": True,
                "message": "You are already logged in.",
                "redirect_url": reverse("home"),
            }, status=200)

        return redirect("home")

    # Allow only GET and POST requests.
    if request.method not in ["GET", "POST"]:
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "Only GET and POST requests are allowed.",
            }, status=405)

        return HttpResponseNotAllowed(["GET", "POST"])

    if request.method == "POST":
        form = SignupForm(request.POST)

        # Validate the submitted registration details.
        if form.is_valid():
            data = form.cleaned_data

            # Hash the password before storing it in the session.
            password_hash = make_password(data["password"])

            # Store the validated signup details temporarily.
            request.session["signup_data"] = {
                "username": data["username"],
                "email": data["email"],
                "phone": data["phone"],
                "password_hash": password_hash,
            }

            # Generate the OTP and its expiry time.
            otp = generate_otp()
            otp_expiry = get_otp_expiry()

            request.session["signup_otp"] = otp
            request.session["signup_otp_expiry"] = (
                otp_expiry.isoformat()
            )

            # Send the OTP to the submitted email address.
            send_otp_email(data["email"], otp)

            # Return JSON if the frontend expects it.
            if wants_json(request):
                return JsonResponse({
                    "success": True,
                    "message": "OTP has been sent to your email address.",
                    "redirect_url": reverse("verify_otp"),
                }, status=202)

            messages.success(
                request,
                "OTP has been sent to your email address.",
            )

            return redirect("verify_otp")

        # Return validation errors as JSON for the frontend.
        if wants_json(request):
            return JsonResponse({
                "success": False,
                "message": "Please correct the signup form errors.",
                "errors": form.errors.get_json_data(),
            }, status=400)

        # Preserve the existing Django messages-based error display.
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)

    else:
        form = SignupForm()

    # Preserve non-password values for the existing template inputs.
    context = {
        "form": form,
        "username": request.POST.get("username", ""),
        "email": request.POST.get("email", ""),
        "phone": request.POST.get("phone", ""),
    }

    # Display the existing signup page.
    return render(request, "accounts/signup.html", context)