from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import TemplateView, CreateView, ListView, DetailView, FormView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
import logging
from django.views import View
from django.db import transaction
from ..models import Requisition, RequisitionApproval, Destination
from ..forms import RequisitionForm, RequisitionItemFormSet, RequisitionApprovalForm, RequisitionFilterForm
from ..utils import generate_po_for_requisition
from ..utils import build_workitem_timeline


logger = logging.getLogger(__name__)


class RequisitionCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """View for a requester to create a new Requisition."""
    model = Requisition
    form_class = RequisitionForm
    template_name = 'supplychain/requisitions/create.html'
    permission_required = 'supplychain.submit_requisition'
    success_url = reverse_lazy('supplychain:requisition-list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["section"] = "requisitions"
        if self.request.POST:
            context['item_formset'] = RequisitionItemFormSet(self.request.POST)
        else:
            context['item_formset'] = RequisitionItemFormSet()
        return context

    def form_valid(self, form):
        # Build context with the bound formset (incl. errors if any)
        context = self.get_context_data(form=form)
        item_formset = context['item_formset']

        # If item formset is invalid, re-render the page with errors
        if not item_formset.is_valid():
            return self.render_to_response(context)

        # Both main form and formset are valid: save everything atomically
        with transaction.atomic():
            self.object = form.save()
            item_formset.instance = self.object
            item_formset.save()

            initial_note = (form.cleaned_data.get('notes') or "").strip()
            if initial_note:
                RequisitionApproval.objects.create(
                    requisition=self.object,
                    approver=self.request.user,
                    action=Requisition.PENDING,
                    notes=f"Requester note: {initial_note}",
                )

        messages.success(
            self.request,
            f"Requisition #{self.object.id} created successfully!"
        )
        return redirect(self.success_url)


    def handle_no_permission(self):
        messages.error(self.request, "You do not have permission to submit requisitions.")
        return super().handle_no_permission()


class RequisitionUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Allow requester to update a queried requisition and resubmit."""
    model = Requisition
    form_class = RequisitionForm
    template_name = 'supplychain/requisitions/update.html'
    permission_required = 'supplychain.submit_requisition'
    success_url = reverse_lazy('supplychain:requisition-list')

    def get_queryset(self):
        return Requisition.objects.filter(
            requester=self.request.user,
            status=Requisition.QUERIED,
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["section"] = "requisitions"

        # Line-item formset
        if self.request.POST:
            context['item_formset'] = RequisitionItemFormSet(
                self.request.POST,
                instance=self.object,
            )
        else:
            context['item_formset'] = RequisitionItemFormSet(
                instance=self.object,
            )

        # --- Audit trail (same idea as detail view) ---
        context["approvals"] = (
            self.object.approvals
            .select_related("approver")
            .order_by("timestamp")
        )
        context["timeline"] = build_workitem_timeline(self.object)

        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        logger.debug("RequisitionUpdateView POST keys: %s", list(request.POST.keys()))
        logger.debug("RequisitionUpdateView FILES keys: %s", list(request.FILES.keys()))
        return super().post(request, *args, **kwargs)

        
    def form_valid(self, form):
        context = self.get_context_data()
        item_formset = context['item_formset']

        if not item_formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form))

        # --- Build a simple summary of item-level changes BEFORE saving ---
        item_changes = []

        for f in item_formset.forms:
            if not f.has_changed():
                continue

            # new item (added)
            if f.instance.pk is None and not f.cleaned_data.get('DELETE', False):
                item_changes.append(
                    f"Added {f.cleaned_data.get('product')} × {f.cleaned_data.get('quantity')}"
                )
                continue

            # deleted item
            if f.cleaned_data.get('DELETE', False):
                # Only log if this row actually existed in the DB
                if f.instance.pk is not None:
                    item_changes.append(
                        f"Removed {f.instance.product} × {f.instance.quantity}"
                    )
                # if pk is None it was never saved, so we just ignore it
                continue

            # updated existing item
            line_bits = []
            if 'product' in f.changed_data:
                line_bits.append(
                    f"product: {f.instance.product} → {f.cleaned_data.get('product')}"
                )
            if 'quantity' in f.changed_data:
                line_bits.append(
                    f"quantity: {f.instance.quantity} → {f.cleaned_data.get('quantity')}"
                )
            if 'supplier' in f.changed_data:
                line_bits.append(
                    f"supplier: {f.instance.supplier} → {f.cleaned_data.get('supplier')}"
                )

            if line_bits:
                item_changes.append(
                    f"Updated item {f.instance.product}: " + "; ".join(line_bits)
                )
        # --- Save requisition + items ---
        self.object = form.save()
        item_formset.instance = self.object
        item_formset.save()

        # Set back to pending
        self.object.status = Requisition.PENDING
        self.object.save(update_fields=['status', 'updated_at'])

        # --- Build the audit note text ---
        requester_reply = (form.cleaned_data.get('notes') or "").strip()
        note_parts = []

        if requester_reply:
            note_parts.append(f"Requester reply: {requester_reply}")

        if item_changes:
            note_parts.append("Changes: " + " | ".join(item_changes))

        if not note_parts:
            note_parts.append("Requisition updated")

        # --- Log a NEW audit entry (conversation continues, nothing overwritten) ---
        RequisitionApproval.objects.create(
            requisition=self.object,
            approver=self.request.user,        # requester here
            action=Requisition.PENDING,
            notes="\n".join(note_parts),
        )

        messages.success(
            self.request,
            f"Requisition #{self.object.id} updated and resubmitted for approval."
        )
        return redirect(self.success_url)
    
    
    def handle_no_permission(self):
        messages.error(self.request, "You do not have permission to update requisitions.")
        return super().handle_no_permission()


class RequisitionListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """List all requisitions where the logged-in user is the requester."""
    model = Requisition
    template_name = 'supplychain/requisitions/list.html'
    context_object_name = 'requisitions'
    permission_required = 'supplychain.submit_requisition'
    paginate_by = 20

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["section"] = "requisitions"
        return context

    def get_queryset(self):
        return Requisition.objects.filter(requester=self.request.user).order_by('-created_at')

    def handle_no_permission(self):
        messages.error(self.request, "You cannot view requisitions.")
        return super().handle_no_permission()


class RequisitionPendingListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """List all Requisitions with status='PENDING'."""
    model = Requisition
    template_name = 'supplychain/requisitions/pending.html'
    context_object_name = 'pending_requisitions'
    permission_required = 'supplychain.approve_requisition'
    paginate_by = 20

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["section"] = "requisitions"
        return context

    def get_queryset(self):
        return Requisition.objects.filter(status=Requisition.PENDING).order_by('created_at')

    def handle_no_permission(self):
        messages.error(self.request, "You do not have permission to approve requisitions.")
        return super().handle_no_permission()


class RequisitionAllListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """List all requisitions regardless of requester with optional filtering."""

    model = Requisition
    template_name = 'supplychain/requisitions/all.html'
    context_object_name = 'requisitions'
    permission_required = 'supplychain.view_all_requisitions'
    paginate_by = 20
    form_class = RequisitionFilterForm

    def get_queryset(self):
        qs = Requisition.objects.all().order_by('-created_at')
        self.filter_form = self.form_class(self.request.GET or None)
        if self.filter_form.is_valid():
            data = self.filter_form.cleaned_data
            if data.get('requester'):
                qs = qs.filter(requester=data['requester'])
            if data.get('start_date'):
                qs = qs.filter(created_at__date__gte=data['start_date'])
            if data.get('end_date'):
                qs = qs.filter(created_at__date__lte=data['end_date'])
            if data.get('destination'):
                qs = qs.filter(destination=data['destination'])
            if data.get('urgent') == 'yes':
                qs = qs.filter(urgent=True)
            elif data.get('urgent') == 'no':
                qs = qs.filter(urgent=False)
            if data.get('status'):
                qs = qs.filter(status=data['status'])
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["section"] = "requisitions"
        context["filter_form"] = getattr(self, 'filter_form', self.form_class())
        return context

    def handle_no_permission(self):
        messages.error(self.request, "You do not have permission to view all requisitions.")
        return super().handle_no_permission()


class RequisitionDetailView(LoginRequiredMixin, View):
    """Show requisition details and optionally approval form."""

    def get(self, request, pk):
        requisition = get_object_or_404(Requisition, pk=pk)
        if (request.user == requisition.requester) or request.user.has_perm('supplychain.approve_requisition'):
            approval_form = None
            can_approve = (
                requisition.status == Requisition.PENDING
                and request.user.has_perm('supplychain.approve_requisition')
            )
            if can_approve:
                approval_form = RequisitionApprovalForm()
            context = {
                'requisition': requisition,
                'items': requisition.items.select_related('product').all(),
                'approvals': requisition.approvals.select_related('approver').order_by('timestamp'),
                'approval_form': approval_form,
                'can_approve': can_approve,
                'section': 'requisitions',
                'timeline': build_workitem_timeline(requisition)
            }
            return render(request, 'supplychain/requisitions/detail.html', context)
        else:
            messages.error(request, "You do not have permission to view this requisition.")
            return redirect('supplychain:requisition-list')

    def post(self, request, pk):
        requisition = get_object_or_404(Requisition, pk=pk)
        if not request.user.has_perm('supplychain.approve_requisition'):
            messages.error(request, "You do not have permission to approve requisitions.")
            return redirect('supplychain:requisition-detail', pk=pk)
        if requisition.status != Requisition.PENDING:
            messages.warning(request, "This requisition has already been processed.")
            return redirect('supplychain:requisition-detail', pk=pk)
        form = RequisitionApprovalForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    form.save(requisition=requisition, approver=request.user)
                    if requisition.status == Requisition.APPROVED:
                        if requisition.destination.name == Destination.PURCHASE:
                            generate_po_for_requisition(
                                requisition, created_by=request.user
                            )
                        # elif requisition.destination.name == Destination.STORE:
                        #     generate_issuance_for_requisition(
                        #         requisition, created_by=request.user
                        #     )
                messages.success(
                    request,
                    f"Requisition #{requisition.id} marked {requisition.status.lower()}.",
                )
                def _notify():
                    try:
                        if requisition.status == Requisition.APPROVED:
                            from ..services.notifications.email_notifications import notify_requisition_approved_to_all
                            notify_requisition_approved_to_all(requisition)
                        elif requisition.status == Requisition.DENIED:
                            from ..services.notifications.email_notifications import notify_requisition_denied_to_all
                            notify_requisition_denied_to_all(requisition)
                    except Exception as exc:
                        logger.exception("Error sending notification for requisition #%s", requisition.id)
                transaction.on_commit(_notify)
            except ValueError as exc:
                messages.error(request, str(exc))
            return redirect('supplychain:requisition-detail', pk=pk)
        else:
            context = {
                'requisition': requisition,
                'items': requisition.items.select_related('product').all(),
                'approvals': requisition.approvals.select_related('approver').order_by('timestamp'),
                'approval_form': form,
                'can_approve': True,
                'section': 'requisitions',
                'timeline': build_workitem_timeline(requisition)
            }
            return render(request, 'supplychain/requisitions/detail.html', context)
        