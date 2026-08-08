from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ai import llm
from ai.forms import AnswerSheetUploadForm, MarksheetFormSet, MarksheetRejectForm, VivaAnswerForm, VivaStartForm
from ai.models import AnswerSheetReview, Marksheet, VivaSession, VivaTurn
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


@student_required
def viva_start(request):
    if request.method == "POST":
        form = VivaStartForm(request.POST, student=request.user)
        if form.is_valid():
            session = VivaSession.objects.create(
                student=request.user,
                course=form.cleaned_data["course"],
                topic=form.cleaned_data["topic"],
            )
            try:
                result = llm.generate_viva_question(session.topic, session.course, [])
                VivaTurn.objects.create(session=session, round_number=1, question=result.get("question", ""))
            except llm.LLMError as exc:
                session.status = VivaSession.Status.COMPLETED
                session.error = str(exc)
                session.save()
                messages.error(request, f"Couldn't start the viva: {exc}")
                return redirect("viva-list")
            return redirect("viva-detail", session.id)
    else:
        form = VivaStartForm(student=request.user)

    return render(request, "ai/viva_start.html", {"form": form})


@student_required
def viva_detail(request, session_id):
    session = get_object_or_404(VivaSession, id=session_id, student=request.user)
    return render(
        request,
        "ai/viva_detail.html",
        {"session": session, "turns": session.turns.all(), "answer_form": VivaAnswerForm()},
    )


@student_required
@require_POST
def viva_answer(request, session_id):
    session = get_object_or_404(VivaSession, id=session_id, student=request.user)
    if session.is_completed:
        return JsonResponse({"error": "This viva has already finished."}, status=400)

    turn = session.current_turn
    if not turn:
        return JsonResponse({"error": "No question is waiting for an answer right now."}, status=400)

    if not turn.is_answered:
        answer = request.POST.get("answer", "").strip()
        if not answer:
            return JsonResponse({"error": "Type or speak an answer first."}, status=400)
        turn.answer = answer
        turn.answered_at = timezone.now()
        turn.save(update_fields=["answer", "answered_at"])
    # else: the turn was already answered by a previous request whose AI call
    # then failed (e.g. a timeout) — this is a retry, so just continue on
    # from the already-saved answer instead of asking for it again.

    transcript = [
        {"question": t.question, "answer": t.answer} for t in session.turns.filter(answered_at__isnull=False)
    ]

    if turn.round_number >= VivaSession.MAX_ROUNDS:
        try:
            result = llm.generate_viva_verdict(session.topic, session.course, transcript)
            session.verdict = result.get("verdict", "")
            session.verdict_summary = result.get("summary", "")
            session.strengths = result.get("strengths", [])
            session.gaps = result.get("gaps", [])
            session.suggestions = result.get("suggestions", "")
        except llm.LLMError as exc:
            session.error = str(exc)
        session.status = VivaSession.Status.COMPLETED
        session.completed_at = timezone.now()
        session.save()

        if session.error:
            return JsonResponse({"error": session.error}, status=503)
        return JsonResponse(
            {
                "type": "verdict",
                "verdict_label": session.get_verdict_display(),
                "verdict": session.verdict,
                "summary": session.verdict_summary,
                "strengths": session.strengths,
                "gaps": session.gaps,
                "suggestions": session.suggestions,
            }
        )

    try:
        result = llm.generate_viva_question(session.topic, session.course, transcript)
    except llm.LLMError as exc:
        return JsonResponse({"error": str(exc)}, status=503)

    next_turn = VivaTurn.objects.create(
        session=session,
        round_number=turn.round_number + 1,
        question=result.get("question", ""),
        probe_reason=result.get("probe_reason", ""),
    )
    return JsonResponse(
        {
            "type": "question",
            "round": next_turn.round_number,
            "max_rounds": VivaSession.MAX_ROUNDS,
            "question": next_turn.question,
            "probe_reason": next_turn.probe_reason,
        }
    )


@student_required
def viva_list(request):
    sessions = VivaSession.objects.filter(student=request.user)
    return render(request, "ai/viva_list.html", {"sessions": sessions})
