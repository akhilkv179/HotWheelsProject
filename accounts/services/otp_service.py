import secrets
from datetime import timedelta
from django.utils import timezone


# Generate a random 6-digit OTP code as a string.
def generate_otp():
    return str(secrets.randbelow(900000) + 100000)

# Calculate the expiration timestamp for an OTP, 5 minutes from now.
def get_otp_expiry():
    return timezone.now() + timedelta(minutes=5)