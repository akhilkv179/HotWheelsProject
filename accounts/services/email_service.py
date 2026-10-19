from django.core.mail import send_mail
from django.conf import settings


# Send an email containing an OTP verification code to the user.
def send_otp_email(email, otp):

    subject = "Hot Wheels - Email Verification"

    message = f"""
Hello,

Your Hot Wheels verification OTP is:

{otp}

This OTP is valid for 1 minute.

If you did not create an account, please ignore this email.

Thank you,
Hot Wheels Team
"""

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [email],
    )