
from django.contrib import messages
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.cache import never_cache

from accounts.forms import SetNewPasswordForm
from accounts.models import User


# Check whether the frontend expects a JSON response.
def wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# Set a new admin password after successful OTP verification.
@never_cache
def admin_set_new_password_view(request):

    # Check whether the admin has verified the OTP.
    if not request.session.get("admin_reset_otp_verified"):

        error_message = "Please verify the OTP first."

        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": error_message,
                    "redirect_url": reverse("admin_forgot_password"),
                },
                status=403,
            )

        messages.error(request, error_message)
        return redirect("admin_forgot_password")

    # Retrieve the email stored during password recovery.
    email = request.session.get("admin_reset_email")

    if not email:

        error_message = (
            "Your password reset session has expired. "
            "Please request a new OTP."
        )

        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": error_message,
                    "redirect_url": reverse("admin_forgot_password"),
                },
                status=410,
            )

        messages.error(request, error_message)
        return redirect("admin_forgot_password")

    # Find the active admin account.
    user = User.objects.filter(
        email__iexact=email,
        is_staff=True,
        is_active=True,
    ).first()

    if user is None:

        error_message = "Admin account not found or inactive."

        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": error_message,
                    "redirect_url": reverse("admin_forgot_password"),
                },
                status=404,
            )

        messages.error(request, error_message)
        return redirect("admin_forgot_password")

    # Allow only GET and POST requests.
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

    if request.method == "POST":

        form = SetNewPasswordForm(
            request.POST,
            user=user,
        )

        # Validate the new password.
        if form.is_valid():

            new_password = form.cleaned_data["new_password"]

            # Hash and save the new password securely.
            user.set_password(new_password)
            user.save()

            # Clear all admin password-reset session data.
            request.session.pop("admin_reset_email", None)
            request.session.pop("admin_reset_otp", None)
            request.session.pop("admin_reset_otp_expiry", None)
            request.session.pop("admin_reset_otp_verified", None)

            if wants_json(request):
                return JsonResponse(
                    {
                        "success": True,
                        "message": "Admin password reset successfully.",
                        "redirect_url": reverse("admin_login"),
                    },
                    status=200,
                )

            messages.success(
                request,
                "Admin password reset successfully.",
            )
            return redirect("admin_login")

        # Return password validation errors as JSON.
        if wants_json(request):
            return JsonResponse(
                {
                    "success": False,
                    "message": "Please correct the password form errors.",
                    "errors": form.errors.get_json_data(),
                },
                status=400,
            )

        # Display validation errors using Django messages.
        for field_errors in form.errors.values():
            for error in field_errors:
                messages.error(request, error)

    else:
        form = SetNewPasswordForm(user=user)

    # Display the admin new-password page.
    return render(
        request,
        "admin_panel/admin_set_new_password.html",
        {"form": form},
    )
