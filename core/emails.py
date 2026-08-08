import logging

from django.conf import settings
from django.core.mail import send_mail

from core.models import EmailOTP

logger = logging.getLogger(__name__)


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


def send_assignment_posted_email(assignment, link=None):
    """Notify every student enrolled in the course that a new assignment is up.

    Best-effort: a flaky SMTP connection shouldn't stop the instructor from
    posting the assignment, so failures are logged rather than raised.
    """
    from courses.models import Enrollment

    recipients = list(
        Enrollment.objects.filter(course=assignment.course)
        .exclude(student__email="")
        .values_list("student__email", flat=True)
        .distinct()
    )
    if not recipients:
        return
    due = assignment.due_date.strftime("%b %d, %Y at %I:%M %p") if assignment.due_date else "No due date set"
    body = (
        f"A new assignment has been posted in {assignment.course.title}.\n\n"
        f"Title: {assignment.title}\n"
        f"Due: {due}\n"
        f"Points: {assignment.max_points}\n"
    )
    if assignment.description:
        body += f"\n{assignment.description}\n"
    if link:
        body += f"\nView it here: {link}\n"
    try:
        send_mail(
            subject=f"New assignment: {assignment.title} ({assignment.course.title})",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL or None,
            recipient_list=recipients,
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send assignment-posted email for assignment %s", assignment.id)


def send_submission_received_email(submission, link=None):
    """Notify the course instructor that a student submitted an assignment."""
    instructor = submission.assignment.course.instructor
    if not instructor.email:
        return
    body = (
        f"{submission.student.first_name or submission.student.email} submitted "
        f"“{submission.assignment.title}” in {submission.assignment.course.title}.\n\n"
        f"Submitted: {submission.submitted_at.strftime('%b %d, %Y at %I:%M %p')}\n"
    )
    if link:
        body += f"\nReview it here: {link}\n"
    try:
        send_mail(
            subject=f"New submission: {submission.assignment.title} — {submission.student.first_name or submission.student.email}",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL or None,
            recipient_list=[instructor.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send submission-received email for submission %s", submission.id)
