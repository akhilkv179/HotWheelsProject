from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache

from ..forms import SignupForm
from ..services.otp_service import generate_otp, get_otp_expiry
from ..services.email_service import send_otp_email


@never_cache
def signup(request):
    """Validate registration data and start email OTP verification."""

    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = SignupForm(request.POST)

        if form.is_valid():
            data = form.cleaned_data

            # Hash the password before storing it in the session.
            password_hash = make_password(data["password"])

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

            messages.success(
                request,
                "OTP has been sent to your email address.",
            )

            return redirect("verify_otp")

        # Keep the existing Django messages-based error display.
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)

    else:
        form = SignupForm()

    # Preserve the non-password values for existing template inputs.
    context = {
        "form": form,
        "username": request.POST.get("username", ""),
        "email": request.POST.get("email", ""),
        "phone": request.POST.get("phone", ""),
    }

    return render(request, "accounts/signup.html", context)