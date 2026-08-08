from django import forms
from django.forms import formset_factory

from ai.models import AnswerSheetReview


class MarksheetEntryForm(forms.Form):
    subject = forms.CharField(
        max_length=100, required=False, widget=forms.TextInput(attrs={"placeholder": "e.g. Mathematics"})
    )
    score = forms.DecimalField(
        required=False, min_value=0, widget=forms.NumberInput(attrs={"placeholder": "78", "step": "0.01"})
    )
    max_score = forms.DecimalField(
        required=False,
        min_value=0,
        initial=100,
        widget=forms.NumberInput(attrs={"placeholder": "100", "step": "0.01"}),
    )

    def clean(self):
        cleaned = super().clean()
        subject = cleaned.get("subject")
        score = cleaned.get("score")
        max_score = cleaned.get("max_score")

        if not subject and score is None and max_score is None:
            cleaned["_blank"] = True
            return cleaned

        if not subject:
            raise forms.ValidationError("Enter a subject name.")
        if score is None or max_score is None:
            raise forms.ValidationError("Enter both a score and a max score.")
        if max_score <= 0:
            raise forms.ValidationError("Max score must be greater than zero.")
        if score > max_score:
            raise forms.ValidationError("Score can't exceed the max score.")
        return cleaned


MarksheetFormSet = formset_factory(MarksheetEntryForm, extra=6)


class MarksheetRejectForm(forms.Form):
    reason = forms.CharField(
        label="Reason",
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Why doesn't this look right? (shown to the student)"}),
    )


MAX_ANSWER_SHEET_SIZE = 10 * 1024 * 1024  # 10MB


class AnswerSheetUploadForm(forms.ModelForm):
    class Meta:
        model = AnswerSheetReview
        fields = ["subject", "image"]
        widgets = {
            "subject": forms.TextInput(attrs={"placeholder": "e.g. Biology Midterm"}),
            "image": forms.ClearableFileInput(attrs={"accept": "image/*"}),
        }

    def clean_image(self):
        image = self.cleaned_data["image"]
        if image.size > MAX_ANSWER_SHEET_SIZE:
            raise forms.ValidationError("That image is too large — please keep it under 10MB.")
        return image
