from django import forms

from courses.models import Announcement, Assignment, Course, Lesson, LessonResource, Submission


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ["title", "description", "is_published"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class LessonForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = ["title", "content", "order"]
        widgets = {"content": forms.Textarea(attrs={"rows": 6})}


class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ["title", "description", "due_date", "max_points"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "due_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class SubmissionForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ["content"]
        widgets = {"content": forms.Textarea(attrs={"rows": 5, "placeholder": "Write your submission here…"})}


class GradeForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ["grade", "feedback"]
        widgets = {"feedback": forms.Textarea(attrs={"rows": 3})}


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ["title", "body"]
        widgets = {"body": forms.Textarea(attrs={"rows": 4})}


class LessonResourceForm(forms.ModelForm):
    class Meta:
        model = LessonResource
        fields = ["kind", "title", "url", "file", "text", "order"]
        widgets = {
            "kind": forms.Select(attrs={"data-resource-kind-select": ""}),
            "text": forms.Textarea(attrs={"rows": 4, "placeholder": "Write the note content…"}),
            "url": forms.URLInput(attrs={"placeholder": "https://youtube.com/watch?v=… or any link"}),
        }

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get("kind")
        if kind in (LessonResource.Kind.VIDEO, LessonResource.Kind.LINK) and not cleaned.get("url"):
            self.add_error("url", "A URL is required for this resource type.")
        if kind == LessonResource.Kind.FILE and not cleaned.get("file"):
            self.add_error("file", "A file is required for this resource type.")
        if kind == LessonResource.Kind.NOTE and not cleaned.get("text"):
            self.add_error("text", "Note content is required.")
        return cleaned
