from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from core.emails import send_otp_email
from core.forms import ResendOTPForm, SignUpForm, OTPVerifyForm
from core.models import User
from courses.models import Announcement, Assignment, Course, Enrollment, Submission


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.save()
            send_otp_email(user)
            messages.success(request, "We've emailed you a 6-digit code. Enter it below to activate your account.")
            return redirect(f"{reverse('verify-otp')}?email={quote(user.email)}")
    else:
        form = SignUpForm()

    return render(request, "core/register.html", {"form": form})


def verify_otp(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    initial = {"email": request.GET.get("email", "")}

    if request.method == "POST":
        form = OTPVerifyForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"].lower()
            code = form.cleaned_data["code"].strip()
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                user = None

            otp = user.otps.filter(code=code).first() if user else None

            if user and otp and otp.is_valid():
                otp.is_used = True
                otp.save(update_fields=["is_used"])
                user.is_active = True
                user.email_verified = True
                user.save(update_fields=["is_active", "email_verified"])
                login(request, user, backend="django.contrib.auth.backends.ModelBackend")
                messages.success(request, "Email verified! Welcome aboard.")
                return redirect("dashboard")
            elif user and otp and otp.is_expired():
                form.add_error("code", "This code has expired. Request a new one below.")
            else:
                form.add_error("code", "That code isn't right. Double-check and try again.")
    else:
        form = OTPVerifyForm(initial=initial)

    return render(request, "core/verify_otp.html", {"form": form})


def resend_otp(request):
    if request.method == "POST":
        form = ResendOTPForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"].lower()
            try:
                user = User.objects.get(email=email, is_active=False)
            except User.DoesNotExist:
                user = None

            if user:
                latest = user.otps.first()
                cooldown = settings.OTP_RESEND_COOLDOWN_SECONDS
                if latest and (timezone.now() - latest.created_at).total_seconds() < cooldown:
                    wait = int(cooldown - (timezone.now() - latest.created_at).total_seconds())
                    messages.error(request, f"Please wait {wait}s before requesting another code.")
                else:
                    send_otp_email(user)
                    messages.success(request, "If that account needs verifying, a new code is on its way.")
            else:
                # Same message whether or not the account exists/is already
                # verified, so this endpoint can't be used to probe emails.
                messages.success(request, "If that account needs verifying, a new code is on its way.")

            return redirect(f"{reverse('verify-otp')}?email={quote(email)}")
    else:
        form = ResendOTPForm(initial={"email": request.GET.get("email", "")})

    return render(request, "core/resend_otp.html", {"form": form})


def _assignment_status(assignment):
    if not assignment.due_date:
        return "neutral"
    remaining = assignment.due_date - timezone.now()
    if remaining.total_seconds() < 0:
        return "critical"
    if remaining.total_seconds() < 3 * 24 * 3600:
        return "warning"
    return "neutral"


@login_required
def dashboard(request):
    user = request.user

    if user.is_instructor:
        courses = Course.objects.filter(instructor=user).order_by("-created_at")
        total_students = Enrollment.objects.filter(course__instructor=user).values("student").distinct().count()
        ungraded_qs = (
            Submission.objects.filter(assignment__course__instructor=user, grade__isnull=True)
            .select_related("assignment", "student", "assignment__course")
            .order_by("submitted_at")
        )
        context = {
            "courses": courses,
            "course_count": courses.count(),
            "total_students": total_students,
            "ungraded_count": ungraded_qs.count(),
            "ungraded_submissions": ungraded_qs[:6],
        }
        return render(request, "core/dashboard_teacher.html", context)

    enrollments = (
        Enrollment.objects.filter(student=user).select_related("course", "course__instructor").order_by("-enrolled_at")
    )
    course_ids = [e.course_id for e in enrollments]
    completed = sum(1 for e in enrollments if e.progress_percent == 100)

    graded = Submission.objects.filter(student=user, grade__isnull=False)
    avg_grade = None
    if graded.exists():
        total_pct = 0
        for s in graded:
            total_pct += (s.grade / s.assignment.max_points) * 100 if s.assignment.max_points else 0
        avg_grade = round(total_pct / graded.count())

    upcoming_qs = (
        Assignment.objects.filter(course_id__in=course_ids)
        .exclude(submissions__student=user)
        .select_related("course")
        .order_by("due_date")[:6]
    )
    upcoming = [{"assignment": a, "status": _assignment_status(a)} for a in upcoming_qs]

    announcements = (
        Announcement.objects.filter(course_id__in=course_ids).select_related("course")[:5]
    )

    context = {
        "enrollments": enrollments,
        "enrolled_count": len(enrollments),
        "completed_count": completed,
        "avg_grade": avg_grade,
        "upcoming": upcoming,
        "announcements": announcements,
    }
    return render(request, "core/dashboard_student.html", context)
