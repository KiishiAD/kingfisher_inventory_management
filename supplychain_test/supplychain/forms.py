from django import forms
from django.forms import inlineformset_factory
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from .models import Requisition, RequisitionItem, Destination, RequisitionApproval , PurchaseOrderApproval, PurchaseOrder,PurchaseOrderItem

class RequisitionForm(forms.ModelForm):
    class Meta:
        model = Requisition
        fields = ['urgent', 'evidence', 'destination', 'notes', 'Supplier_destination_sub_category']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
        # Exclude: 'requester', 'status' (default pending)

    def __init__(self, *args, **kwargs):
        # Optionally, we could pass 'request' into kwargs to set requester
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)


    def clean(self):
        cleaned_data = super().clean()
        destination = cleaned_data.get('destination')
        sub_category = cleaned_data.get('Supplier_destination_sub_category')

        if destination and sub_category:
            if destination.name == destination.STORE and sub_category.name in ["CONSUMABLES", "SERVICES"]:
                error_msg =  "Supplier sub category should be empty when destination is STORE."
                self.add_error('Supplier_destination_sub_category', error_msg)

        return cleaned_data

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
    fields=['product', 'quantity', 'supplier'],
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
        Apply the chosen action to the requisition, record an audit trail, and return the updated Requisition instance.
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


User = get_user_model()


class RequisitionFilterForm(forms.Form):
    """Filters for the All Requisitions page."""

    requester = forms.ModelChoiceField(
        queryset=User.objects.all(), required=False, label=_("Requester")
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        label=_("Start Date"),
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        label=_("End Date"),
    )
    destination = forms.ModelChoiceField(
        queryset=Destination.objects.all(), required=False, label=_("Destination")
    )
    urgent = forms.ChoiceField(
        choices=[("", "---------"), ("yes", "Yes"), ("no", "No")],
        required=False,
        label=_("Urgent"),
    )
    status = forms.ChoiceField(
        choices=[("", "---------")] + Requisition.STATUS_CHOICES,
        required=False,
        label=_("Status"),
    )




class PurchaseOrderApprovalForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrderApproval
        fields = ["action", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Lock choices to COO-level actions only
        self.fields["action"].choices = [
            (PurchaseOrder.APPROVED, "Approve"),
            (PurchaseOrder.DENIED, "Deny"),
            (PurchaseOrder.QUERIED, "Query"),
        ]

    def save(self, *, purchase_order, approver, commit=True):
        self.instance.purchase_order = purchase_order
        self.instance.approver = approver
        return super().save(commit=commit)

class PurchaseOrderItemForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrderItem
        fields = ['product', 'quantity', 'unit_cost']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make unit_cost read-only in the UI; still submitted as a normal field.
        self.fields['unit_cost'].widget.attrs['readonly'] = 'readonly'



class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ['requisition', 'supplier']  # 'requisition' optional

PurchaseOrderItemFormSet = inlineformset_factory(
    PurchaseOrder,
    PurchaseOrderItem,
    form=PurchaseOrderItemForm,
    fields=['product', 'quantity', 'unit_cost'],
    extra=1,
    can_delete=True,
)
