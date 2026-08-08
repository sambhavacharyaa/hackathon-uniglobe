from django.conf import settings
from django.db import models


class Marksheet(models.Model):
    """A student-submitted set of subject scores plus the AI's review of them."""

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="marksheets"
    )
    entries = models.JSONField(help_text="List of {subject, score, max_score}")
    created_at = models.DateTimeField(auto_now_add=True)

    # Filled in once the AI review succeeds.
    overall_summary = models.TextField(blank=True)
    strengths = models.JSONField(default=list, blank=True)
    weaknesses = models.JSONField(default=list, blank=True)
    student_suggestions = models.TextField(blank=True)
    teacher_suggestions = models.TextField(blank=True)

    is_reviewed = models.BooleanField(default=False)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Marksheet for {self.student.email} ({self.created_at:%Y-%m-%d})"

    @property
    def average_percent(self):
        if not self.entries:
            return None
        total = sum(e["max_score"] for e in self.entries)
        obtained = sum(e["score"] for e in self.entries)
        if not total:
            return None
        return round(obtained * 100 / total)


class ChatThread(models.Model):
    """One AI doubt-solving conversation between a student and a course's assistant."""

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_threads"
    )
    course = models.ForeignKey("courses.Course", on_delete=models.CASCADE, related_name="chat_threads")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("student", "course")

    def __str__(self):
        return f"{self.student.email} — {self.course.title} chat"


class ChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "Student"
        MODEL = "model", "Assistant"

    thread = models.ForeignKey(ChatThread, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"
