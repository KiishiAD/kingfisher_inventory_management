from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import TemplateView, CreateView, ListView, DetailView, FormView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.views import View
from django.db import transaction
from ..utils import *
from ..models import *
from ..forms import *


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
        context = self.get_context_data()
        item_formset = context['item_formset']
        if item_formset.is_valid():
            self.object = form.save()
            item_formset.instance = self.object
            item_formset.save()
            messages.success(
                self.request,
                f"Requisition #{self.object.id} created successfully!"
            )
            return redirect(self.success_url)
        else:
            return self.render_to_response(self.get_context_data(form=form))

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
        return Requisition.objects.filter(requester=self.request.user, status=Requisition.QUERIED)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["section"] = "requisitions"
        if self.request.POST:
            context['item_formset'] = RequisitionItemFormSet(self.request.POST, instance=self.object)
        else:
            context['item_formset'] = RequisitionItemFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        item_formset = context['item_formset']
        if item_formset.is_valid():
            self.object = form.save()
            item_formset.instance = self.object
            item_formset.save()
            self.object.status = Requisition.PENDING
            self.object.save(update_fields=['status', 'updated_at'])
            RequisitionApproval.objects.create(
                requisition=self.object,
                approver=self.request.user,
                action=Requisition.PENDING,
                notes='Requisition updated'
            )
            messages.success(self.request, f"Requisition #{self.object.id} updated and resubmitted for approval.")
            return redirect(self.success_url)
        else:
            return self.render_to_response(self.get_context_data(form=form))

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
                        if requisition.destination.name == Destination.SUPPLIER:
                            generate_po_for_requisition(
                                requisition, created_by=request.user
                            )
                        elif requisition.destination.name == Destination.STORE:
                            generate_issuance_for_requisition(
                                requisition, created_by=request.user
                            )
                messages.success(
                    request,
                    f"Requisition #{requisition.id} marked {requisition.status.lower()}.",
                )
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
            }
            return render(request, 'supplychain/requisitions/detail.html', context)
