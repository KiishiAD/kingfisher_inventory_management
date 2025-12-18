from django import forms
from django.contrib.auth.models import Group

class InviteUserForm(forms.Form):
    email = forms.EmailField()
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
