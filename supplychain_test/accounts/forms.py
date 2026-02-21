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
    password = forms.CharField(widget=forms.PasswordInput, label="Password")
    confirm_password = forms.CharField(widget=forms.PasswordInput, label="Confirm password")

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
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")

        if password:
            validate_password(password)

        return cleaned_data


class OrganizationSetupForm(forms.Form):
    organization_name = forms.CharField(max_length=255)

    def clean_organization_name(self):
        name = self.cleaned_data["organization_name"].strip()
        if Organization.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError("An organization with this name already exists.")
        return name
