from django.contrib import admin

from ai.models import AnswerSheetReview, ChatMessage, ChatThread, Marksheet, VivaSession, VivaTurn


@admin.register(Marksheet)
class MarksheetAdmin(admin.ModelAdmin):
    list_display = ("student", "average_percent", "status", "is_reviewed", "reviewed_by", "created_at")
    list_filter = ("status", "is_reviewed")
    search_fields = ("student__email",)
    readonly_fields = ("created_at",)


@admin.register(AnswerSheetReview)
class AnswerSheetReviewAdmin(admin.ModelAdmin):
    list_display = ("student", "subject", "is_reviewed", "created_at")
    list_filter = ("is_reviewed",)
    search_fields = ("student__email", "subject")
    readonly_fields = ("created_at",)


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(ChatThread)
class ChatThreadAdmin(admin.ModelAdmin):
    list_display = ("student", "course", "created_at")
    search_fields = ("student__email", "course__title")
    inlines = [ChatMessageInline]


class VivaTurnInline(admin.TabularInline):
    model = VivaTurn
    extra = 0
    readonly_fields = ("created_at", "answered_at")


@admin.register(VivaSession)
class VivaSessionAdmin(admin.ModelAdmin):
    list_display = ("student", "topic", "course", "status", "verdict", "created_at")
    list_filter = ("status", "verdict")
    search_fields = ("student__email", "topic")
    inlines = [VivaTurnInline]
