import secrets
from datetime import timedelta
from django.utils import timezone


def generate_otp():
    return str(secrets.randbelow(900000) + 100000)

def get_otp_expiry():
    return timezone.now() + timedelta(minutes=1)