from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from ai import llm
from ai.forms import MarksheetFormSet
from ai.models import Marksheet
from courses.decorators import student_required


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
                try:
                    result = llm.review_marksheet(entries, request.user.first_name or request.user.email)
                    marksheet.overall_summary = result.get("overall_summary", "")
                    marksheet.strengths = result.get("strengths", [])
                    marksheet.weaknesses = result.get("weaknesses", [])
                    marksheet.student_suggestions = result.get("student_suggestions", "")
                    marksheet.teacher_suggestions = result.get("teacher_suggestions", "")
                    marksheet.is_reviewed = True
                except llm.LLMError as exc:
                    marksheet.error = str(exc)
                marksheet.save()

                if marksheet.error:
                    messages.error(request, marksheet.error)
                else:
                    messages.success(request, "Your marksheet has been reviewed.")
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
