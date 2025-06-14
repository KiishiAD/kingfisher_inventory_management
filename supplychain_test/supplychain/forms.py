from django import forms
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _
from .models import *

class RequisitionForm(forms.ModelForm):
    class Meta:
        model = Requisition
        fields = ['urgent', 'evidence', 'destination', 'notes']
        # Exclude: 'requester', 'status' (default pending)

    def __init__(self, *args, **kwargs):
        # Optionally, we could pass 'request' into kwargs to set requester
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.request and not instance.requester_id:
            instance.requester = self.request.user
        if commit:
            instance.save()
        return instance
    
# We will allow up to 10 line items by default; you can adjust max_num as needed.
RequisitionItemFormSet = inlineformset_factory(
    parent_model=Requisition,
    model=RequisitionItem,
    fields=['product', 'quantity'],
    extra=1,
    can_delete=True,
    max_num=10,
)


from django.utils.translation import gettext_lazy as _

class RequisitionApprovalForm(forms.Form):
    ACTION_CHOICES = [
        (Requisition.APPROVED, _('Approve')),
        (Requisition.DENIED, _('Deny')),
        (Requisition.QUERIED, _('Query')),
    ]

    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.RadioSelect,
        label=_("Action")
    )
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        label=_("Notes / Comments")
    )

    def save(self, requisition, approver):
        """
        Apply the chosen action to the requisition, record an audit trail,
        send notifications, and return the updated Requisition instance.
        """
        action = self.cleaned_data['action']
        notes = self.cleaned_data.get('notes', '').strip()

        # 1. Update the Requisition status
        requisition.status = action
        requisition.save(update_fields=['status', 'updated_at'])

        # 2. Create a RequisitionApproval audit record
        RequisitionApproval.objects.create(
            requisition=requisition,
            approver=approver,
            action=action,
            notes=notes,
        )

        return requisition
