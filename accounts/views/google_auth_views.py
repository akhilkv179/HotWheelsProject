
from django.conf import settings
from django.shortcuts import redirect
from urllib.parse import urlencode
from django.contrib.auth import login
from django.contrib import messages
from django.views.decorators.cache import never_cache

import secrets
import requests

from ..models import User


# Redirect the user to Google OAuth login with a secure state token.
@never_cache
def google_login(request):

    if request.user.is_authenticated:
        return redirect("home")

    action = request.GET.get("action")

    if action not in ["signup", "login"]:
        messages.error(
            request,
            "Invalid Google authentication request."
        )
        return redirect("login")

    request.session["google_auth_action"] = action

    state = secrets.token_urlsafe(32)
    request.session["google_oauth_state"] = state

    google_authorization_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
    )

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
    }

    authorization_url = (
        google_authorization_url
        + "?"
        + urlencode(params)
    )

    return redirect(authorization_url)


# Handle Google's callback, authenticate or register the user,
# and sign them in.
@never_cache
def google_callback(request):

    state = request.GET.get("state")
    code = request.GET.get("code")

    stored_state = request.session.get("google_oauth_state")
    action = request.session.get("google_auth_action")

    # Choose the appropriate page for authentication errors.
    fallback_url = (
        "signup" if action == "signup" else "login"
    )

    # Validate OAuth state to prevent CSRF attacks.
    if not state or not stored_state or state != stored_state:
        request.session.pop("google_oauth_state", None)
        request.session.pop("google_auth_action", None)

        messages.error(
            request,
            "Invalid Google authentication request."
        )
        return redirect("login")

    # The state has been validated; do not reuse it.
    request.session.pop("google_oauth_state", None)

    if action not in ["signup", "login"]:
        request.session.pop("google_auth_action", None)
        messages.error(
            request,
            "Invalid Google authentication request."
        )
        return redirect("login")

    # Handle cases where the user cancels Google's consent screen.
    if not code:
        request.session.pop("google_auth_action", None)
        messages.error(
            request,
            "Google authentication was cancelled or failed."
        )
        return redirect(fallback_url)

    token_url = "https://oauth2.googleapis.com/token"

    token_data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    # Exchange the authorization code for an access token.
    try:
        token_response = requests.post(
            token_url,
            data=token_data,
            timeout=15,
        )
        token_response.raise_for_status()
        tokens = token_response.json()

    except (requests.RequestException, ValueError):
        request.session.pop("google_auth_action", None)
        messages.error(
            request,
            "Could not connect to Google's authentication service. "
            "Please try again."
        )
        return redirect(fallback_url)

    access_token = tokens.get("access_token")

    if not access_token:
        request.session.pop("google_auth_action", None)
        messages.error(
            request,
            "Google did not provide an access token."
        )
        return redirect(fallback_url)

    userinfo_url = (
        "https://openidconnect.googleapis.com/v1/userinfo"
    )

    # Retrieve the Google account information.
    try:
        userinfo_response = requests.get(
            userinfo_url,
            headers={
                "Authorization": f"Bearer {access_token}"
            },
            timeout=15,
        )
        userinfo_response.raise_for_status()
        google_user = userinfo_response.json()

    except (requests.RequestException, ValueError):
        request.session.pop("google_auth_action", None)
        messages.error(
            request,
            "Could not retrieve your Google account information. "
            "Please try again."
        )
        return redirect(fallback_url)

    email = (google_user.get("email") or "").strip().lower()
    name = (google_user.get("name") or "").strip()

    if not email:
        request.session.pop("google_auth_action", None)
        messages.error(
            request,
            "Google account email was not received."
        )
        return redirect(fallback_url)

    # Find an existing account using its email address.
    user = User.objects.filter(email__iexact=email).first()

    if not user:
        # Use Google's name, or the email prefix if no name is supplied.
        username_base = (
            name.replace(" ", "").lower()
            if name
            else email.split("@")[0].lower()
        )

        # Ensure the username is not empty.
        username_base = username_base or "googleuser"
        username = username_base
        count = 1

        while User.objects.filter(username=username).exists():
            username = f"{username_base}{count}"
            count += 1

        user = User(
            username=username,
            email=email,
        )
        user.set_unusable_password()
        user.save()

    # Check the standard Django active flag and the project's block flag.
    if not user.is_active or getattr(user, "is_blocked", False):
        request.session.pop("google_auth_action", None)
        messages.error(
            request,
            "Your account is blocked or inactive."
        )
        return redirect("login")

    # Authenticate the user through Django.
    login(request, user)

    request.session.pop("google_auth_action", None)

    return redirect("home")
