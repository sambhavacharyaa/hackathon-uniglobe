from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from ai import llm
from ai.forms import AnswerSheetUploadForm, MarksheetFormSet, MarksheetRejectForm
from ai.models import AnswerSheetReview, Marksheet
from courses.decorators import instructor_required, student_required
from courses.models import Enrollment


@student_required
def marksheet_upload(request):
    if request.method == "POST":
        formset = MarksheetFormSet(request.POST)
        if formset.is_valid():
            entries = []
            for form in formset:
                cleaned = form.cleaned_data
                if not cleaned or cleaned.get("_blank"):
                    continue
                entries.append(
                    {
                        "subject": cleaned["subject"],
                        "score": float(cleaned["score"]),
                        "max_score": float(cleaned["max_score"]),
                    }
                )

            if not entries:
                messages.error(request, "Add at least one subject with a score.")
            else:
                marksheet = Marksheet.objects.create(student=request.user, entries=entries)
                messages.success(
                    request,
                    "Submitted. A teacher needs to approve your scores before the AI review runs.",
                )
                return redirect("marksheet-detail", marksheet.id)
    else:
        formset = MarksheetFormSet()

    return render(request, "ai/marksheet_upload.html", {"formset": formset})


@student_required
def marksheet_detail(request, marksheet_id):
    marksheet = get_object_or_404(Marksheet, id=marksheet_id, student=request.user)
    return render(request, "ai/marksheet_detail.html", {"marksheet": marksheet})


@student_required
def marksheet_list(request):
    marksheets = Marksheet.objects.filter(student=request.user)
    return render(request, "ai/marksheet_list.html", {"marksheets": marksheets})


def _run_ai_review(marksheet):
    """Call the AI and populate the review fields. Caller is responsible for save()."""
    try:
        result = llm.review_marksheet(marksheet.entries, marksheet.student.first_name or marksheet.student.email)
        marksheet.overall_summary = result.get("overall_summary", "")
        marksheet.strengths = result.get("strengths", [])
        marksheet.weaknesses = result.get("weaknesses", [])
        marksheet.student_suggestions = result.get("student_suggestions", "")
        marksheet.teacher_suggestions = result.get("teacher_suggestions", "")
        marksheet.is_reviewed = True
        marksheet.error = ""
    except llm.LLMError as exc:
        marksheet.error = str(exc)


def _teacher_can_review(teacher, marksheet):
    return Enrollment.objects.filter(course__instructor=teacher, student_id=marksheet.student_id).exists()


@instructor_required
def marksheet_review_queue(request):
    student_ids = Enrollment.objects.filter(course__instructor=request.user).values_list(
        "student_id", flat=True
    )
    pending = (
        Marksheet.objects.filter(student_id__in=student_ids, status=Marksheet.Status.PENDING)
        .select_related("student")
    )
    reject_forms = {m.id: MarksheetRejectForm() for m in pending}
    recent = (
        Marksheet.objects.filter(student_id__in=student_ids)
        .exclude(status=Marksheet.Status.PENDING)
        .select_related("student", "reviewed_by")[:8]
    )
    return render(
        request,
        "ai/review_queue.html",
        {"pending": pending, "reject_forms": reject_forms, "recent": recent},
    )


@instructor_required
def approve_marksheet(request, marksheet_id):
    marksheet = get_object_or_404(Marksheet, id=marksheet_id)
    if not _teacher_can_review(request.user, marksheet):
        messages.error(request, "You can only review marksheets from your own students.")
        return redirect("marksheet-review-queue")
    if not marksheet.is_pending:
        messages.error(request, "That marksheet has already been reviewed.")
        return redirect("marksheet-review-queue")

    if request.method == "POST":
        marksheet.status = Marksheet.Status.APPROVED
        marksheet.reviewed_by = request.user
        marksheet.reviewed_at = timezone.now()
        _run_ai_review(marksheet)
        marksheet.save()
        if marksheet.error:
            messages.error(request, f"Approved, but the AI review failed: {marksheet.error}")
        else:
            messages.success(request, f"Approved {marksheet.student.email}'s marksheet and generated the AI review.")
    return redirect("marksheet-review-queue")


@instructor_required
def reject_marksheet(request, marksheet_id):
    marksheet = get_object_or_404(Marksheet, id=marksheet_id)
    if not _teacher_can_review(request.user, marksheet):
        messages.error(request, "You can only review marksheets from your own students.")
        return redirect("marksheet-review-queue")
    if not marksheet.is_pending:
        messages.error(request, "That marksheet has already been reviewed.")
        return redirect("marksheet-review-queue")

    if request.method == "POST":
        form = MarksheetRejectForm(request.POST)
        if form.is_valid():
            marksheet.status = Marksheet.Status.REJECTED
            marksheet.reviewed_by = request.user
            marksheet.reviewed_at = timezone.now()
            marksheet.rejection_reason = form.cleaned_data["reason"]
            marksheet.save()
            messages.success(request, f"Rejected {marksheet.student.email}'s marksheet.")
        else:
            messages.error(request, "Please give a reason for the rejection.")
    return redirect("marksheet-review-queue")


@student_required
def answer_sheet_upload(request):
    if request.method == "POST":
        form = AnswerSheetUploadForm(request.POST, request.FILES)
        if form.is_valid():
            review = form.save(commit=False)
            review.student = request.user
            review.save()

            try:
                review.image.seek(0)
                result = llm.review_answer_sheet(review.image.read(), review.subject)
                review.transcription = result.get("transcription", "")
                review.overall_feedback = result.get("overall_feedback", "")
                review.strengths = result.get("strengths", [])
                review.mistakes = result.get("mistakes", [])
                review.improvement_suggestions = result.get("improvement_suggestions", "")
                review.is_reviewed = True
            except llm.LLMError as exc:
                review.error = str(exc)
            review.save()

            if review.error:
                messages.error(request, review.error)
            else:
                messages.success(request, "Your answer sheet has been reviewed.")
            return redirect("answer-sheet-detail", review.id)
    else:
        form = AnswerSheetUploadForm()

    return render(request, "ai/answer_sheet_upload.html", {"form": form})


@student_required
def answer_sheet_detail(request, review_id):
    review = get_object_or_404(AnswerSheetReview, id=review_id, student=request.user)
    return render(request, "ai/answer_sheet_detail.html", {"review": review})


@student_required
def answer_sheet_list(request):
    reviews = AnswerSheetReview.objects.filter(student=request.user)
    return render(request, "ai/answer_sheet_list.html", {"reviews": reviews})
