from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password

from .models import Organization

User = get_user_model()


class InviteUserForm(forms.Form):
    email = forms.EmailField()
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )


class OrganizationSignupForm(forms.Form):
    organization_name = forms.CharField(max_length=255)
    email = forms.EmailField()
    password1 = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_organization_name(self):
        name = self.cleaned_data["organization_name"].strip()
        if Organization.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError("An organization with this name already exists.")
        return name

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords do not match.")

        if password1:
            validate_password(password1)

        return cleaned_data


class OrganizationSetupForm(forms.Form):
    organization_name = forms.CharField(max_length=255)

    def clean_organization_name(self):
        name = self.cleaned_data["organization_name"].strip()
        if Organization.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError("An organization with this name already exists.")
        return name
