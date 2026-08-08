from django.conf import settings
from django.db import models


class Marksheet(models.Model):
    """A student-submitted set of subject scores plus the AI's review of them.

    Scores are self-reported, so a student could enter inflated marks. To
    keep the AI review meaningful, a teacher who shares a course with the
    student must approve the raw scores before the AI ever sees them —
    the AI review only runs at approval time, not at upload time.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending approval"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="marksheets"
    )
    entries = models.JSONField(help_text="List of {subject, score, max_score}")
    created_at = models.DateTimeField(auto_now_add=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="marksheet_reviews",
        help_text="The teacher who approved or rejected this marksheet.",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)

    # Filled in once a teacher approves and the AI review succeeds.
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

    @property
    def is_pending(self):
        return self.status == self.Status.PENDING

    @property
    def is_approved(self):
        return self.status == self.Status.APPROVED

    @property
    def is_rejected(self):
        return self.status == self.Status.REJECTED


class AnswerSheetReview(models.Model):
    """A photographed/scanned exam answer sheet plus the AI's review of it.

    Unlike Marksheet, this doesn't go through a teacher-approval gate: it's
    a photo of something the student actually wrote, not a self-reported
    number, so there's much less to fake.
    """

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="answer_sheet_reviews"
    )
    subject = models.CharField(max_length=150, help_text="e.g. \"Biology Midterm\"")
    image = models.ImageField(upload_to="answer_sheets/")
    created_at = models.DateTimeField(auto_now_add=True)

    # Filled in once the AI review succeeds.
    transcription = models.TextField(blank=True)
    overall_feedback = models.TextField(blank=True)
    strengths = models.JSONField(default=list, blank=True)
    mistakes = models.JSONField(default=list, blank=True)
    improvement_suggestions = models.TextField(blank=True)

    is_reviewed = models.BooleanField(default=False)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subject} — {self.student.email} ({self.created_at:%Y-%m-%d})"


class VivaSession(models.Model):
    """An adaptive oral-exam (viva voce) session.

    The AI asks an opening question on a topic, then for a few rounds reads
    the student's latest answer and probes whatever was vague or
    memorized-sounding about it — not a fixed question list. After the last
    round it renders a verdict on whether the understanding looked genuine.
    """

    MAX_ROUNDS = 3

    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "In progress"
        COMPLETED = "completed", "Completed"

    class Verdict(models.TextChoices):
        STRONG = "strong", "Genuine understanding"
        DEVELOPING = "developing", "Developing understanding"
        ROTE = "rote", "Memorized, not understood"
        WEAK = "weak", "Significant gaps"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="viva_sessions"
    )
    course = models.ForeignKey(
        "courses.Course", on_delete=models.SET_NULL, null=True, blank=True, related_name="viva_sessions"
    )
    topic = models.CharField(max_length=200)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.IN_PROGRESS)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Filled in once the final round is graded.
    verdict = models.CharField(max_length=12, choices=Verdict.choices, blank=True)
    verdict_summary = models.TextField(blank=True)
    strengths = models.JSONField(default=list, blank=True)
    gaps = models.JSONField(default=list, blank=True)
    suggestions = models.TextField(blank=True)

    error = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Viva: {self.topic} — {self.student.email}"

    @property
    def is_completed(self):
        return self.status == self.Status.COMPLETED

    @property
    def current_turn(self):
        """The most recent turn — the one still awaiting an answer while in progress."""
        return self.turns.order_by("-round_number").first()


class VivaTurn(models.Model):
    session = models.ForeignKey(VivaSession, on_delete=models.CASCADE, related_name="turns")
    round_number = models.PositiveIntegerField()
    question = models.TextField()
    probe_reason = models.CharField(
        max_length=200, blank=True, help_text="Why the AI is asking this — shown as a small hint."
    )
    answer = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["round_number"]
        unique_together = ("session", "round_number")

    def __str__(self):
        return f"Round {self.round_number}: {self.question[:50]}"

    @property
    def is_answered(self):
        return bool(self.answered_at)


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
