from django.urls import path

from ai import views

urlpatterns = [
    path("", views.marksheet_list, name="marksheet-list"),
    path("upload/", views.marksheet_upload, name="marksheet-upload"),
    path("<int:marksheet_id>/", views.marksheet_detail, name="marksheet-detail"),
]
