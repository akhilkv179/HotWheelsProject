from django.contrib import messages
from django.shortcuts import redirect,render
from ..models import User
from django.utils import timezone
from datetime import datetime
from ..services.otp_service import generate_otp, get_otp_expiry
from datetime import datetime, timedelta
from ..services.email_service import send_otp_email


def verify_otp(request):
    if request.method == "POST":
        entered_otp = request.POST.get("otp", "").strip()

        stored_otp = request.session.get("signup_otp")
        stored_expiry = request.session.get("signup_otp_expiry")

        signup_data = request.session.get("signup_data")

        # Check whether signup session data exists.
        if not stored_otp or not signup_data:
            messages.error(request, "Signup session has expired.")
            return redirect("signup")

        # Check whether expiry time exists.
        if not stored_expiry:
            messages.error(request, "OTP has expired.")
            return redirect("signup")

        # Convert the stored string back into a datetime object.
        expiry_time = datetime.fromisoformat(stored_expiry)

        # Check whether the OTP has expired.
        if timezone.now() > expiry_time:
            messages.error(
                request,
                "OTP has expired. Please request a new OTP."
            )
            return redirect("verify_otp")

        # Check whether the entered OTP is correct.
        if entered_otp == stored_otp:

            # Create the user after successful OTP verification.
            user = User(
                username=signup_data["username"],
                email=signup_data["email"],
                phone=signup_data["phone"],
                password=signup_data["password_hash"],
            )

            user.save()

            # Remove temporary signup data from the session.
            request.session.pop("signup_otp", None)
            request.session.pop("signup_otp_expiry", None)
            request.session.pop("last_otp_resend", None)
            request.session.pop("signup_data", None)

            messages.success(
                request,
                "Account created successfully."
            )

            return redirect("login")

        # OTP entered by the user is incorrect.
        messages.error(request, "Invalid OTP.")

    # Get the expiry time from the session.
        # Get the OTP expiry time from the session.
    stored_expiry = request.session.get("signup_otp_expiry")

    remaining_seconds = 0

    if stored_expiry:
        expiry_time = datetime.fromisoformat(stored_expiry)

        # Calculate how many seconds are left.
        remaining_seconds = int(
            (expiry_time - timezone.now()).total_seconds()
        )

        # Don't allow a negative value.
        if remaining_seconds < 0:
            remaining_seconds = 0

    return render(
        request,
        "accounts/verify_otp.html",
        {
            "remaining_seconds": remaining_seconds
        }
    )

def resend_otp(request):
    signup_data = request.session.get("signup_data")


    if not signup_data:
        messages.error(request,"Signup session has expired.")
        return redirect("signup")

    last_resend = request.session.get("last_otp_resend")

    if last_resend:
        last_resend_time = datetime.fromisoformat(last_resend)
        time_passed = timezone.now() - last_resend_time

        if time_passed < timedelta(seconds=30):
            messages.error(
                request,
                "please wait 30 seconds before requesting another otp."
            )
            return redirect("verify_otp")
    
    request.session["last_otp_resend"] = timezone.now().isoformat()

    otp = generate_otp()

    otp_expiry = get_otp_expiry()

    request.session["signup_otp"] = otp 
    request.session["signup_otp_expiry"] = otp_expiry.isoformat()

    send_otp_email(signup_data["email"], otp)

    messages.success(request,"A new otp has been sent.")

    return redirect("verify_otp")