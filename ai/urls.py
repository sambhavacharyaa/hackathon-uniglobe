from django.urls import path

from ai import views

urlpatterns = [
    path("", views.marksheet_list, name="marksheet-list"),
    path("upload/", views.marksheet_upload, name="marksheet-upload"),
    path("review-queue/", views.marksheet_review_queue, name="marksheet-review-queue"),
    path("<int:marksheet_id>/", views.marksheet_detail, name="marksheet-detail"),
    path("<int:marksheet_id>/approve/", views.approve_marksheet, name="marksheet-approve"),
    path("<int:marksheet_id>/reject/", views.reject_marksheet, name="marksheet-reject"),
    path("answer-sheets/", views.answer_sheet_list, name="answer-sheet-list"),
    path("answer-sheets/upload/", views.answer_sheet_upload, name="answer-sheet-upload"),
    path("answer-sheets/<int:review_id>/", views.answer_sheet_detail, name="answer-sheet-detail"),
    path("viva/", views.viva_list, name="viva-list"),
    path("viva/start/", views.viva_start, name="viva-start"),
    path("viva/<int:session_id>/", views.viva_detail, name="viva-detail"),
    path("viva/<int:session_id>/answer/", views.viva_answer, name="viva-answer"),
]
