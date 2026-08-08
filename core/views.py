from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from ai.models import AnswerSheetReview, Marksheet
from core.content import get_landing_context
from core.emails import send_otp_email
from core.forms import ResendOTPForm, SignUpForm, OTPVerifyForm
from core.models import User
from courses.models import (
    Announcement,
    Assignment,
    Course,
    Enrollment,
    LessonProgress,
    Quiz,
    QuizAttempt,
    Submission,
)


def landing(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return render(request, "landing.html", get_landing_context())


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


def _grade_badge_class(percent):
    if percent >= 70:
        return "badge-good"
    if percent >= 40:
        return "badge-warning"
    return "badge-critical"


def _grade_tier(percent):
    """good/warning/critical — used both for the badge class suffix and to
    bucket scores into the analytics distribution."""
    if percent >= 70:
        return "good"
    if percent >= 40:
        return "warning"
    return "critical"


MARKSHEET_BADGE_CLASS = {
    Marksheet.Status.PENDING: "badge-warning",
    Marksheet.Status.APPROVED: "badge-good",
    Marksheet.Status.REJECTED: "badge-critical",
}


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
        return _teacher_dashboard(request)
    return _student_dashboard(request)


def _teacher_dashboard(request):
    user = request.user

    courses = Course.objects.filter(instructor=user).order_by("-created_at")
    student_ids = list(Enrollment.objects.filter(course__instructor=user).values_list("student_id", flat=True))
    total_students = len(set(student_ids))

    ungraded_qs = (
        Submission.objects.filter(assignment__course__instructor=user, grade__isnull=True)
        .select_related("assignment", "student", "assignment__course")
        .order_by("submitted_at")
    )
    pending_marksheets = Marksheet.objects.filter(
        student_id__in=student_ids, status=Marksheet.Status.PENDING
    ).count()

    # Per-course average progress, so a teacher can see at a glance which
    # classes are moving and which have stalled.
    course_performance = []
    for course in courses[:6]:
        course_enrollments = list(course.enrollments.all())
        if course_enrollments:
            avg_progress = round(sum(e.progress_percent for e in course_enrollments) / len(course_enrollments))
        else:
            avg_progress = 0
        course_performance.append(
            {"course": course, "avg_progress": avg_progress, "student_count": len(course_enrollments)}
        )

    activity = []
    for e in (
        Enrollment.objects.filter(course__instructor=user)
        .select_related("student", "course")
        .order_by("-enrolled_at")[:6]
    ):
        activity.append(
            {
                "icon": "🎒",
                "text": f"{e.student.first_name or e.student.email} enrolled in {e.course.title}",
                "meta": e.student.email,
                "url": reverse("course-detail", args=[e.course.slug]),
                "timestamp": e.enrolled_at,
                "badge": None,
                "badge_class": None,
            }
        )
    for s in (
        Submission.objects.filter(assignment__course__instructor=user)
        .select_related("student", "assignment__course")
        .order_by("-submitted_at")[:6]
    ):
        activity.append(
            {
                "icon": "📥",
                "text": f"{s.student.first_name or s.student.email} submitted “{s.assignment.title}”",
                "meta": s.assignment.course.title,
                "url": reverse("view-submissions", args=[s.assignment.course.slug, s.assignment_id]),
                "timestamp": s.submitted_at,
                "badge": "Graded" if s.is_graded else "Ungraded",
                "badge_class": "badge-good" if s.is_graded else "badge-warning",
            }
        )
    for m in Marksheet.objects.filter(student_id__in=student_ids).select_related("student").order_by("-created_at")[:6]:
        activity.append(
            {
                "icon": "📊",
                "text": f"{m.student.first_name or m.student.email} submitted a marksheet",
                "meta": f"{len(m.entries)} subject{'s' if len(m.entries) != 1 else ''}",
                "url": reverse("marksheet-review-queue"),
                "timestamp": m.created_at,
                "badge": m.get_status_display(),
                "badge_class": MARKSHEET_BADGE_CLASS[m.status],
            }
        )
    for qa in (
        QuizAttempt.objects.filter(quiz__lesson__course__instructor=user)
        .select_related("student", "quiz", "quiz__lesson__course")
        .order_by("-completed_at")[:6]
    ):
        activity.append(
            {
                "icon": "📝",
                "text": f"{qa.student.first_name or qa.student.email} scored {qa.score_percent}% on “{qa.quiz.title}”",
                "meta": qa.quiz.lesson.course.title,
                "url": reverse("course-detail", args=[qa.quiz.lesson.course.slug]),
                "timestamp": qa.completed_at,
                "badge": f"{qa.score_percent}%",
                "badge_class": _grade_badge_class(qa.score_percent),
            }
        )
    activity.sort(key=lambda a: a["timestamp"], reverse=True)

    # --------------------------------------------------------------------
    # Analytics: quiz performance per quiz, marksheet performance per
    # subject (aggregated across every approved marksheet), and a
    # good/warning/critical distribution across every quiz attempt.
    # --------------------------------------------------------------------
    quiz_stats = []
    all_quiz_percents = []
    quizzes = Quiz.objects.filter(lesson__course__instructor=user).select_related("lesson", "lesson__course")
    for quiz in quizzes:
        attempts = list(quiz.attempts.all())
        if not attempts:
            continue
        percents = [a.score_percent for a in attempts]
        all_quiz_percents.extend(percents)
        avg_score = round(sum(percents) / len(percents))
        quiz_stats.append(
            {
                "title": quiz.title,
                "course": quiz.lesson.course.title,
                "avg_score": avg_score,
                "attempt_count": len(attempts),
                "tier": _grade_tier(avg_score),
            }
        )
    quiz_stats.sort(key=lambda q: q["avg_score"])

    tier_counts = {"good": 0, "warning": 0, "critical": 0}
    for pct in all_quiz_percents:
        tier_counts[_grade_tier(pct)] += 1

    subject_scores = {}
    approved_marksheets = Marksheet.objects.filter(
        student_id__in=student_ids, status=Marksheet.Status.APPROVED, is_reviewed=True
    )
    marksheet_averages = []
    for m in approved_marksheets:
        if m.average_percent is not None:
            marksheet_averages.append(m.average_percent)
        for e in m.entries:
            if e.get("max_score"):
                pct = e["score"] * 100 / e["max_score"]
                subject_scores.setdefault(e["subject"], []).append(pct)

    marksheet_stats = [
        {
            "subject": subject,
            "avg_score": round(sum(pcts) / len(pcts)),
            "count": len(pcts),
            "tier": _grade_tier(round(sum(pcts) / len(pcts))),
        }
        for subject, pcts in subject_scores.items()
    ]
    marksheet_stats.sort(key=lambda s: s["avg_score"])

    context = {
        "courses": courses,
        "course_count": courses.count(),
        "total_students": total_students,
        "ungraded_count": ungraded_qs.count(),
        "ungraded_submissions": ungraded_qs[:6],
        "pending_marksheets": pending_marksheets,
        "course_performance": course_performance,
        "activity": activity[:8],
        "quiz_stats": quiz_stats[:10],
        "marksheet_stats": marksheet_stats[:10],
        "tier_counts": tier_counts,
        "total_quiz_attempts": len(all_quiz_percents),
        "avg_quiz_score": round(sum(all_quiz_percents) / len(all_quiz_percents)) if all_quiz_percents else None,
        "total_approved_marksheets": len(marksheet_averages),
        "avg_marksheet_score": round(sum(marksheet_averages) / len(marksheet_averages)) if marksheet_averages else None,
    }
    return render(request, "core/dashboard_teacher.html", context)


def _student_dashboard(request):
    user = request.user

    enrollments = (
        Enrollment.objects.filter(student=user).select_related("course", "course__instructor").order_by("-enrolled_at")
    )
    course_ids = [e.course_id for e in enrollments]
    completed = sum(1 for e in enrollments if e.progress_percent == 100)
    continue_course = next((e for e in enrollments if e.progress_percent < 100), None)

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

    activity = []
    for qa in (
        QuizAttempt.objects.filter(student=user)
        .select_related("quiz", "quiz__lesson__course")
        .order_by("-completed_at")[:6]
    ):
        activity.append(
            {
                "icon": "📝",
                "text": f"Scored {qa.score_percent}% on “{qa.quiz.title}”",
                "meta": qa.quiz.lesson.course.title,
                "url": reverse("take-quiz", args=[qa.quiz.lesson.course.slug, qa.quiz.lesson_id]),
                "timestamp": qa.completed_at,
                "badge": f"{qa.score_percent}%",
                "badge_class": _grade_badge_class(qa.score_percent),
            }
        )
    for lp in (
        LessonProgress.objects.filter(student=user).select_related("lesson", "lesson__course").order_by("-completed_at")[:6]
    ):
        activity.append(
            {
                "icon": "✅",
                "text": f"Completed “{lp.lesson.title}”",
                "meta": lp.lesson.course.title,
                "url": reverse("course-detail", args=[lp.lesson.course.slug]),
                "timestamp": lp.completed_at,
                "badge": None,
                "badge_class": None,
            }
        )
    for m in Marksheet.objects.filter(student=user).order_by("-created_at")[:6]:
        ts = m.reviewed_at or m.created_at
        text = {
            Marksheet.Status.PENDING: "Submitted a marksheet for approval",
            Marksheet.Status.APPROVED: "Marksheet approved & AI-reviewed",
            Marksheet.Status.REJECTED: "Marksheet was rejected",
        }[m.status]
        activity.append(
            {
                "icon": "📊",
                "text": text,
                "meta": f"{len(m.entries)} subject{'s' if len(m.entries) != 1 else ''}",
                "url": reverse("marksheet-detail", args=[m.id]),
                "timestamp": ts,
                "badge": m.get_status_display(),
                "badge_class": MARKSHEET_BADGE_CLASS[m.status],
            }
        )
    for a in AnswerSheetReview.objects.filter(student=user).order_by("-created_at")[:6]:
        if a.is_reviewed:
            text, badge, bclass = f"Answer sheet reviewed: {a.subject}", "Reviewed", "badge-good"
        elif a.error:
            text, badge, bclass = f"Answer sheet review failed: {a.subject}", "Failed", "badge-critical"
        else:
            text, badge, bclass = f"Uploaded an answer sheet: {a.subject}", "Processing", "badge-neutral"
        activity.append(
            {
                "icon": "📄",
                "text": text,
                "meta": "Answer sheet",
                "url": reverse("answer-sheet-detail", args=[a.id]),
                "timestamp": a.created_at,
                "badge": badge,
                "badge_class": bclass,
            }
        )
    for s in (
        Submission.objects.filter(student=user, grade__isnull=False)
        .select_related("assignment", "assignment__course")
        .order_by("-graded_at")[:6]
    ):
        percent = round(s.grade * 100 / s.assignment.max_points) if s.assignment.max_points else 0
        activity.append(
            {
                "icon": "🎓",
                "text": f"Graded {s.grade}/{s.assignment.max_points} on “{s.assignment.title}”",
                "meta": s.assignment.course.title,
                "url": reverse("course-detail", args=[s.assignment.course.slug]),
                "timestamp": s.graded_at,
                "badge": f"{percent}%",
                "badge_class": _grade_badge_class(percent),
            }
        )
    activity.sort(key=lambda a: a["timestamp"], reverse=True)

    context = {
        "enrollments": enrollments,
        "enrolled_count": len(enrollments),
        "completed_count": completed,
        "avg_grade": avg_grade,
        "upcoming": upcoming,
        "announcements": announcements,
        "continue_course": continue_course,
        "activity": activity[:8],
    }
    return render(request, "core/dashboard_student.html", context)
