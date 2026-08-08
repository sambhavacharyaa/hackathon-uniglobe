from django.conf import settings
from django.core.mail import send_mail

from core.models import EmailOTP


def send_otp_email(user):
    """Generate a fresh OTP for the user and email it. Returns the OTP instance."""
    otp = EmailOTP.generate_for(user)
    send_mail(
        subject="Your verification code",
        message=(
            f"Hi {user.first_name or user.email},\n\n"
            f"Your verification code is: {otp.code}\n"
            f"It expires in {settings.OTP_VALIDITY_MINUTES} minutes.\n\n"
            "If you didn't request this, you can ignore this email."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL or None,
        recipient_list=[user.email],
        fail_silently=False,
    )
    return otp
