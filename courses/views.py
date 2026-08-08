from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from ai import llm
from ai.models import ChatMessage, ChatThread, Marksheet
from core.emails import send_assignment_posted_email, send_submission_received_email
from courses.decorators import instructor_required, student_required
from courses.forms import (
    AnnouncementForm,
    AssignmentForm,
    CourseForm,
    GradeForm,
    LessonForm,
    LessonResourceForm,
    SubmissionForm,
)
from courses.models import (
    Assignment,
    Course,
    Enrollment,
    Lesson,
    LessonProgress,
    LessonResource,
    Quiz,
    QuizAttempt,
    QuizQuestion,
    Submission,
)


def _owned_course_or_404(request, slug):
    """Fetch a course and 404/redirect unless the current user teaches it."""
    course = get_object_or_404(Course, slug=slug)
    if course.instructor_id != request.user.id:
        messages.error(request, "You don't manage this course.")
        return None
    return course


@student_required
def catalog(request):
    enrolled_ids = Enrollment.objects.filter(student=request.user).values_list("course_id", flat=True)
    courses = Course.objects.filter(is_published=True).exclude(id__in=enrolled_ids).select_related("instructor")
    return render(request, "courses/catalog.html", {"courses": courses})


@student_required
def enroll(request, slug):
    course = get_object_or_404(Course, slug=slug, is_published=True)
    if request.method == "POST":
        Enrollment.objects.get_or_create(student=request.user, course=course)
        messages.success(request, f"You're enrolled in {course.title}.")
        return redirect("course-detail", slug=course.slug)
    return redirect("catalog")


@login_required
def course_detail(request, slug):
    course = get_object_or_404(Course, slug=slug)

    if request.user.is_instructor:
        if course.instructor_id != request.user.id:
            messages.error(request, "You don't manage this course.")
            return redirect("dashboard")
        lessons = course.lessons.select_related("quiz").prefetch_related("resources")
        assignments = course.assignments.all()
        roster = course.enrollments.select_related("student")
        announcements = course.announcements.all()[:10]
        student_ids = roster.values_list("student_id", flat=True)
        has_insight_ids = set(
            Marksheet.objects.filter(student_id__in=student_ids, is_reviewed=True).values_list(
                "student_id", flat=True
            )
        )
        return render(
            request,
            "courses/course_detail_teacher.html",
            {
                "course": course,
                "lessons": lessons,
                "assignments": assignments,
                "roster": roster,
                "announcements": announcements,
                "has_insight_ids": has_insight_ids,
            },
        )

    enrollment = Enrollment.objects.filter(student=request.user, course=course).first()
    if not enrollment:
        messages.error(request, "Enroll in this course to view it.")
        return redirect("catalog")

    lessons = course.lessons.select_related("quiz").prefetch_related("resources")
    completed_ids = set(
        LessonProgress.objects.filter(student=request.user, lesson__course=course).values_list(
            "lesson_id", flat=True
        )
    )
    assignments = course.assignments.all()
    submissions_by_assignment = {
        s.assignment_id: s for s in Submission.objects.filter(student=request.user, assignment__course=course)
    }
    announcements = course.announcements.all()[:10]

    best_attempt_by_quiz = {}
    for attempt in QuizAttempt.objects.filter(student=request.user, quiz__lesson__course=course):
        existing = best_attempt_by_quiz.get(attempt.quiz_id)
        if not existing or attempt.score_percent > existing.score_percent:
            best_attempt_by_quiz[attempt.quiz_id] = attempt

    return render(
        request,
        "courses/course_detail_student.html",
        {
            "course": course,
            "lessons": lessons,
            "completed_ids": completed_ids,
            "assignments": assignments,
            "submissions_by_assignment": submissions_by_assignment,
            "announcements": announcements,
            "progress_percent": enrollment.progress_percent,
            "submission_form": SubmissionForm(),
            "best_attempt_by_quiz": best_attempt_by_quiz,
        },
    )


@student_required
def complete_lesson(request, slug, lesson_id):
    course = get_object_or_404(Course, slug=slug)
    if not Enrollment.objects.filter(student=request.user, course=course).exists():
        messages.error(request, "Enroll in this course first.")
        return redirect("catalog")
    lesson = get_object_or_404(Lesson, id=lesson_id, course=course)
    if request.method == "POST":
        LessonProgress.objects.get_or_create(student=request.user, lesson=lesson)
    return redirect("course-detail", slug=slug)


@instructor_required
def create_course(request):
    if request.method == "POST":
        form = CourseForm(request.POST)
        if form.is_valid():
            course = form.save(commit=False)
            course.instructor = request.user
            course.save()
            messages.success(request, f"{course.title} created.")
            return redirect("course-detail", slug=course.slug)
    else:
        form = CourseForm()
    return render(request, "courses/course_form.html", {"form": form})


@instructor_required
def add_lesson(request, slug):
    course = _owned_course_or_404(request, slug)
    if course is None:
        return redirect("dashboard")
    if request.method == "POST":
        form = LessonForm(request.POST)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.course = course
            lesson.save()
            messages.success(request, f"Lesson “{lesson.title}” added.")
            return redirect("course-detail", slug=slug)
    else:
        form = LessonForm(initial={"order": course.lesson_count + 1})
    return render(request, "courses/lesson_form.html", {"form": form, "course": course})


@instructor_required
def add_assignment(request, slug):
    course = _owned_course_or_404(request, slug)
    if course is None:
        return redirect("dashboard")
    if request.method == "POST":
        form = AssignmentForm(request.POST)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.course = course
            assignment.save()
            link = request.build_absolute_uri(reverse("course-detail", args=[slug]))
            send_assignment_posted_email(assignment, link=link)
            messages.success(request, f"Assignment “{assignment.title}” posted. Enrolled students have been emailed.")
            return redirect("course-detail", slug=slug)
    else:
        form = AssignmentForm()
    return render(request, "courses/assignment_form.html", {"form": form, "course": course})


@instructor_required
def add_announcement(request, slug):
    course = _owned_course_or_404(request, slug)
    if course is None:
        return redirect("dashboard")
    if request.method == "POST":
        form = AnnouncementForm(request.POST)
        if form.is_valid():
            announcement = form.save(commit=False)
            announcement.course = course
            announcement.author = request.user
            announcement.save()
            messages.success(request, "Announcement posted.")
            return redirect("course-detail", slug=slug)
    else:
        form = AnnouncementForm()
    return render(request, "courses/announcement_form.html", {"form": form, "course": course})


@student_required
def submit_assignment(request, slug, assignment_id):
    course = get_object_or_404(Course, slug=slug)
    if not Enrollment.objects.filter(student=request.user, course=course).exists():
        messages.error(request, "Enroll in this course first.")
        return redirect("catalog")
    assignment = get_object_or_404(Assignment, id=assignment_id, course=course)

    if request.method == "POST":
        form = SubmissionForm(request.POST)
        if form.is_valid():
            submission, created = Submission.objects.get_or_create(
                assignment=assignment, student=request.user, defaults={"content": form.cleaned_data["content"]}
            )
            if not created:
                if submission.is_graded:
                    messages.error(request, "This assignment has already been graded.")
                    return redirect("course-detail", slug=slug)
                submission.content = form.cleaned_data["content"]
                submission.submitted_at = timezone.now()
                submission.save()
            link = request.build_absolute_uri(
                reverse("view-submissions", args=[slug, assignment.id])
            )
            send_submission_received_email(submission, link=link)
            messages.success(request, f"Submitted “{assignment.title}”.")
    return redirect("course-detail", slug=slug)


@instructor_required
def view_submissions(request, slug, assignment_id):
    course = _owned_course_or_404(request, slug)
    if course is None:
        return redirect("dashboard")
    assignment = get_object_or_404(Assignment, id=assignment_id, course=course)
    submissions = assignment.submissions.select_related("student")
    grade_forms = {s.id: GradeForm(instance=s) for s in submissions}
    return render(
        request,
        "courses/submissions.html",
        {"course": course, "assignment": assignment, "submissions": submissions, "grade_forms": grade_forms},
    )


@instructor_required
def grade_submission(request, slug, submission_id):
    course = _owned_course_or_404(request, slug)
    if course is None:
        return redirect("dashboard")
    submission = get_object_or_404(Submission, id=submission_id, assignment__course=course)
    if request.method == "POST":
        form = GradeForm(request.POST, instance=submission)
        if form.is_valid():
            graded = form.save(commit=False)
            graded.graded_at = timezone.now()
            graded.save()
            messages.success(request, f"Graded {submission.student.email}.")
    return redirect("view-submissions", slug=slug, assignment_id=submission.assignment_id)


@instructor_required
def add_resource(request, slug, lesson_id):
    course = _owned_course_or_404(request, slug)
    if course is None:
        return redirect("dashboard")
    lesson = get_object_or_404(Lesson, id=lesson_id, course=course)
    if request.method == "POST":
        form = LessonResourceForm(request.POST, request.FILES)
        if form.is_valid():
            resource = form.save(commit=False)
            resource.lesson = lesson
            resource.save()
            messages.success(request, f"Added “{resource.title}” to {lesson.title}.")
            return redirect("course-detail", slug=slug)
    else:
        form = LessonResourceForm(initial={"kind": LessonResource.Kind.NOTE})
    return render(request, "courses/resource_form.html", {"form": form, "course": course, "lesson": lesson})


@instructor_required
def generate_quiz(request, slug, lesson_id):
    course = _owned_course_or_404(request, slug)
    if course is None:
        return redirect("dashboard")
    lesson = get_object_or_404(Lesson, id=lesson_id, course=course)

    if request.method == "POST":
        try:
            result = llm.generate_quiz(lesson)
        except llm.LLMError as exc:
            messages.error(request, str(exc))
            return redirect("course-detail", slug=slug)

        quiz, _ = Quiz.objects.get_or_create(lesson=lesson)
        quiz.title = result.get("title") or f"Quiz: {lesson.title}"
        quiz.save()
        quiz.questions.all().delete()
        for i, q in enumerate(result.get("questions", [])):
            choices = q.get("choices") or []
            correct_index = q.get("correct_index")
            if len(choices) != 4 or not isinstance(correct_index, int) or not (0 <= correct_index < 4):
                continue
            QuizQuestion.objects.create(
                quiz=quiz,
                text=q.get("text", ""),
                choices=choices,
                correct_index=correct_index,
                explanation=q.get("explanation", ""),
                order=i,
            )
        if quiz.question_count == 0:
            quiz.delete()
            messages.error(request, "The AI didn't return a usable quiz. Please try again.")
        else:
            messages.success(request, f"Generated a {quiz.question_count}-question quiz for “{lesson.title}”.")

    return redirect("course-detail", slug=slug)


@student_required
def take_quiz(request, slug, lesson_id):
    course = get_object_or_404(Course, slug=slug)
    if not Enrollment.objects.filter(student=request.user, course=course).exists():
        messages.error(request, "Enroll in this course first.")
        return redirect("catalog")
    lesson = get_object_or_404(Lesson, id=lesson_id, course=course)
    quiz = get_object_or_404(Quiz, lesson=lesson)
    questions = list(quiz.questions.all())

    result = None
    if request.method == "POST":
        answers = {}
        correct_count = 0
        for q in questions:
            chosen = request.POST.get(f"question_{q.id}")
            chosen_index = int(chosen) if chosen is not None and chosen != "" else None
            answers[str(q.id)] = chosen_index
            if chosen_index == q.correct_index:
                correct_count += 1
        result = QuizAttempt.objects.create(
            quiz=quiz,
            student=request.user,
            answers=answers,
            correct_count=correct_count,
            total_questions=len(questions),
        )

    return render(
        request,
        "courses/take_quiz.html",
        {"course": course, "lesson": lesson, "quiz": quiz, "questions": questions, "result": result},
    )


@login_required
def course_chat(request, slug):
    course = get_object_or_404(Course, slug=slug)
    if not request.user.is_student or not Enrollment.objects.filter(student=request.user, course=course).exists():
        messages.error(request, "Enroll in this course to use the AI assistant.")
        return redirect("dashboard")
    thread, _ = ChatThread.objects.get_or_create(student=request.user, course=course)
    return render(request, "courses/chat.html", {"course": course, "thread_messages": thread.messages.all()})


@student_required
@require_POST
def chat_send(request, slug):
    course = get_object_or_404(Course, slug=slug)
    if not Enrollment.objects.filter(student=request.user, course=course).exists():
        return JsonResponse({"error": "Enroll in this course first."}, status=403)
    message = request.POST.get("message", "").strip()
    if not message:
        return JsonResponse({"error": "Message can't be empty."}, status=400)

    thread, _ = ChatThread.objects.get_or_create(student=request.user, course=course)
    history = [{"role": m.role, "content": m.content} for m in thread.messages.all()]
    ChatMessage.objects.create(thread=thread, role=ChatMessage.Role.USER, content=message)

    try:
        reply = llm.chat_reply(course, history, message)
    except llm.LLMError as exc:
        return JsonResponse({"error": str(exc)}, status=503)

    ChatMessage.objects.create(thread=thread, role=ChatMessage.Role.MODEL, content=reply)
    return JsonResponse({"reply": reply})


@instructor_required
def student_insight(request, slug, user_id):
    course = _owned_course_or_404(request, slug)
    if course is None:
        return redirect("dashboard")
    enrollment = get_object_or_404(Enrollment, course=course, student_id=user_id)
    marksheet = Marksheet.objects.filter(student_id=user_id, is_reviewed=True).first()
    return render(
        request,
        "courses/student_insight.html",
        {"course": course, "student": enrollment.student, "marksheet": marksheet},
    )
