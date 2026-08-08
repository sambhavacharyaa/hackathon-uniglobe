from django import forms
from django.contrib.auth.forms import UserCreationForm

from core.models import User


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    role = forms.ChoiceField(
        choices=[
            (User.Role.STUDENT, "Student"),
            (User.Role.INSTRUCTOR, "Instructor"),
        ],
        widget=forms.RadioSelect,
        initial=User.Role.STUDENT,
    )

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "role", "password1", "password2")

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class OTPVerifyForm(forms.Form):
    email = forms.EmailField(widget=forms.HiddenInput)
    code = forms.CharField(
        label="Verification code",
        max_length=10,
        widget=forms.TextInput(attrs={"autocomplete": "one-time-code", "inputmode": "numeric"}),
    )


class ResendOTPForm(forms.Form):
    email = forms.EmailField()
