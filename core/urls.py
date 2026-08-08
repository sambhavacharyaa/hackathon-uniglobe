from django.contrib.auth import views as auth_views
from django.urls import path

from core import views

urlpatterns = [
    path("", views.landing, name="landing"),
    path("register/", views.register, name="register"),
    path("verify-otp/", views.verify_otp, name="verify-otp"),
    path("resend-otp/", views.resend_otp, name="resend-otp"),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
]
