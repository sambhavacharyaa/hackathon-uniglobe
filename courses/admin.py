from django.contrib import admin

from courses.models import (
    Announcement,
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


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 0


class AssignmentInline(admin.TabularInline):
    model = Assignment
    extra = 0


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("title", "instructor", "is_published", "student_count", "lesson_count", "created_at")
    list_filter = ("is_published",)
    search_fields = ("title", "instructor__email")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [LessonInline, AssignmentInline]


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("student", "course", "enrolled_at", "progress_percent")
    search_fields = ("student__email", "course__title")


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("student", "assignment", "submitted_at", "grade", "is_graded")
    list_filter = ("assignment__course",)
    search_fields = ("student__email", "assignment__title")


class QuizQuestionInline(admin.TabularInline):
    model = QuizQuestion
    extra = 0


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ("title", "lesson", "question_count", "created_at")
    inlines = [QuizQuestionInline]


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ("student", "quiz", "correct_count", "total_questions", "score_percent", "completed_at")
    search_fields = ("student__email", "quiz__title")


@admin.register(LessonResource)
class LessonResourceAdmin(admin.ModelAdmin):
    list_display = ("title", "lesson", "kind", "order", "created_at")
    list_filter = ("kind",)


admin.site.register(Lesson)
admin.site.register(LessonProgress)
admin.site.register(Announcement)
