from django.urls import path

from courses import views

urlpatterns = [
    path("", views.catalog, name="catalog"),
    path("new/", views.create_course, name="create-course"),
    path("<slug:slug>/", views.course_detail, name="course-detail"),
    path("<slug:slug>/enroll/", views.enroll, name="enroll"),
    path("<slug:slug>/lessons/add/", views.add_lesson, name="add-lesson"),
    path("<slug:slug>/lessons/<int:lesson_id>/complete/", views.complete_lesson, name="complete-lesson"),
    path("<slug:slug>/lessons/<int:lesson_id>/resources/add/", views.add_resource, name="add-resource"),
    path("<slug:slug>/lessons/<int:lesson_id>/quiz/generate/", views.generate_quiz, name="generate-quiz"),
    path("<slug:slug>/lessons/<int:lesson_id>/quiz/", views.take_quiz, name="take-quiz"),
    path("<slug:slug>/assignments/add/", views.add_assignment, name="add-assignment"),
    path(
        "<slug:slug>/assignments/<int:assignment_id>/submit/",
        views.submit_assignment,
        name="submit-assignment",
    ),
    path(
        "<slug:slug>/assignments/<int:assignment_id>/submissions/",
        views.view_submissions,
        name="view-submissions",
    ),
    path("<slug:slug>/submissions/<int:submission_id>/grade/", views.grade_submission, name="grade-submission"),
    path("<slug:slug>/announcements/add/", views.add_announcement, name="add-announcement"),
    path("<slug:slug>/chat/", views.course_chat, name="course-chat"),
    path("<slug:slug>/chat/send/", views.chat_send, name="chat-send"),
    path("<slug:slug>/students/<int:user_id>/insight/", views.student_insight, name="student-insight"),
]
