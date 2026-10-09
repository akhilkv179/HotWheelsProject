from django.conf import settings
from django.shortcuts import redirect
from urllib.parse import urlencode
# ^ this converts a python dictionary into URL query parameters 
from django.contrib.auth import login
import secrets
from django.contrib import messages
from ..models import User
import requests
from django.views.decorators.cache import never_cache
# ^This Python library allows your Django server to make HTTP requests to Google's servers.


@never_cache
def google_login(request):

    if request.user.is_authenticated:
        return redirect("home")

    action = request.GET.get("action")

    if action not in ["signup", "login"]:
        messages.error(request, "Invalid Google authentication request.")
        return redirect("login")

    request.session["google_auth_action"] = action

    # This creates a random, temporary string.
    state = secrets.token_urlsafe(32)

    request.session["google_oauth_state"] = state

    google_authorization_url = "https://accounts.google.com/o/oauth2/v2/auth"

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
@never_cache
def google_callback(request):

    state = request.GET.get("state")
    code = request.GET.get("code")

    stored_state = request.session.get("google_oauth_state")

    if not state or state != stored_state:
        messages.error(request, "Invalid Google authentication request.")
        return redirect("signup")

    if not code:
        messages.error(request, "Google authentication failed.")
        return redirect("signup")
    
    token_url = "https://oauth2.googleapis.com/token"

    token_data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    token_response = requests.post(
        token_url,
        data=token_data,
    )

    if token_response.status_code != 200:
        messages.error(request, "Could not authenticate with Google.")
        return redirect("signup")

    tokens = token_response.json()

    access_token = tokens.get("access_token")

    if not access_token:
        messages.error(request, "Google did not provide an access token.")
        return redirect("signup")

    userinfo_url = "https://openidconnect.googleapis.com/v1/userinfo"

    userinfo_response = requests.get(
        userinfo_url,
        headers={
            "Authorization": f"Bearer {access_token}"
        },
    )

    if userinfo_response.status_code != 200:
        messages.error(request, "Could not get your Google account information.")
        return redirect("signup")

    google_user = userinfo_response.json()

    email = google_user.get("email")
    name = google_user.get("name")

    if not email:
        messages.error(request, "Google account email was not received.")
        return redirect("signup")

    user = User.objects.filter(email__iexact=email).first()

    if not user:
        username = name.replace(" ", "").lower()
        original_username = username
        count = 1

        while User.objects.filter(username=username).exists():
            username = f"{original_username}{count}"
            count += 1

        user = User.objects.create(
        username=username,
        email=email,
        )

        user.set_unusable_password()
        user.save()

    if user.is_blocked:
        messages.error(request, "Your account has been blocked.")
        return redirect("login")

    login(request, user)

    request.session.pop("google_oauth_state", None)

    return redirect("home")

