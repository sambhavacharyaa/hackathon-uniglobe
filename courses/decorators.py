from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def instructor_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_instructor:
            messages.error(request, "That page is for instructors only.")
            return redirect("dashboard")
        return view_func(request, *args, **kwargs)

    return wrapper


def student_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_student:
            messages.error(request, "That page is for students only.")
            return redirect("dashboard")
        return view_func(request, *args, **kwargs)

    return wrapper
