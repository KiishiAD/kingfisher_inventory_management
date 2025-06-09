from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import TemplateView, CreateView, ListView, DetailView, FormView
from django.urls import reverse_lazy
from django.contrib import messages
from django.views import View
from .utils import *

from .models import *
from .forms import *

#### Dashboard

class DashboardView(LoginRequiredMixin, TemplateView):
    """
    Simple dashboard that shows:
      - how many requisitions this user has created
      - how many pending requisitions exist (if the user has approver permission)
      - how many low-stock alerts are active
    """
    template_name = "supplychain/dashboard.html"
    # If not logged in, redirect to /accounts/login/ by default.
    # You can also set login_url explicitly:
    # login_url = reverse_lazy('login')

    def get_context_data(self, **kwargs):
        # First get the default context
        context = super().get_context_data(**kwargs)

        # Count how many Requisitions this user has submitted
        user_reqs = Requisition.objects.filter(requester=self.request.user)
        context["user_reqs_count"] = user_reqs.count()

        # If the user has permission to approve requisitions, count all pending ones
        if self.request.user.has_perm("supplychain.approve_requisition"):
            context["pending_reqs_count"] = Requisition.objects.filter(
                status=Requisition.PENDING
            ).count()
        else:
            context["pending_reqs_count"] = 0

        # Count unacknowledged low-stock alerts
        context["low_stock_count"] = LowStockAlert.objects.filter(
            acknowledged=False
        ).count()

        return context
    




###### Requisitions
class RequisitionCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """
    View for a requester to create a new Requisition (header + line items).
    """
    model = Requisition
    form_class = RequisitionForm
    template_name = 'supplychain/requisitions/create.html'
    permission_required = 'supplychain.submit_requisition'
    success_url = reverse_lazy('supplychain:requisition-list')

    def get_form_kwargs(self):
        """
        Pass the HTTP request to RequisitionForm so we can set `requester=request.user`.
        """
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_context_data(self, **kwargs):
        """
        Add the inline formset for RequisitionItem.
        """
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['item_formset'] = RequisitionItemFormSet(
                self.request.POST
            )
        else:
            context['item_formset'] = RequisitionItemFormSet()
        return context

    def form_valid(self, form):
        """
        Called when both RequisitionForm and formset are valid.
        """
        context = self.get_context_data()
        item_formset = context['item_formset']

        if item_formset.is_valid():
            # 1. Save the Requisition header (form.save() will set requester)
            self.object = form.save()

            # 2. Assign the FK on each formset instance, then save
            item_formset.instance = self.object
            item_formset.save()

            messages.success(
                self.request,
                f"Requisition #{self.object.id} created successfully!"
            )
            return redirect(self.success_url)
        else:
            # If formset has errors, re-render the page with errors
            return self.render_to_response(
                self.get_context_data(form=form)
            )

    def handle_no_permission(self):
        messages.error(
            self.request,
            "You do not have permission to submit requisitions."
        )
        return super().handle_no_permission()
    

class RequisitionListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    List all requisitions where the logged-in user is the requester.
    """
    model = Requisition
    template_name = 'supplychain/requisitions/list.html'
    context_object_name = 'requisitions'
    permission_required = 'supplychain.submit_requisition'
    paginate_by = 20

    def get_queryset(self):
        return Requisition.objects.filter(requester=self.request.user).order_by('-created_at')

    def handle_no_permission(self):
        messages.error(self.request, "You cannot view requisitions.")
        return super().handle_no_permission()
    

class RequisitionPendingListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    List all Requisitions with status='PENDING'.
    Shown to users with approve_requisition permission (Procurement role).
    """
    model = Requisition
    template_name = 'supplychain/requisitions/pending.html'
    context_object_name = 'pending_requisitions'
    permission_required = 'supplychain.approve_requisition'
    paginate_by = 20

    def get_queryset(self):
        return Requisition.objects.filter(status=Requisition.PENDING).order_by('created_at')

    def handle_no_permission(self):
        messages.error(self.request, "You do not have permission to approve requisitions.")
        return super().handle_no_permission()




class RequisitionDetailView(LoginRequiredMixin, View):
    """
    Show requisition details (header + items + audit trail).
    If user has 'approve_requisition' and requisition.status == PENDING,
    show the RequisitionApprovalForm.
    """

    def get(self, request, pk):
        requisition = get_object_or_404(Requisition, pk=pk)

        # Check if user can view this requisition:
        # - The requester can view their own requisitions
        # - Procurement (with approve_requisition) can view any
        if (request.user == requisition.requester) or request.user.has_perm('supplychain.approve_requisition'):
            # Build forms/contexts
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
                'approvals': requisition.approvals.select_related('approver').order_by('-timestamp'),
                'approval_form': approval_form,
                'can_approve': can_approve,
            }
            return render(request, 'supplychain/requisitions/detail.html', context)
        else:
            messages.error(request, "You do not have permission to view this requisition.")
            return redirect('supplychain:requisition-list')

    def post(self, request, pk):
        """
        Handle Procurement’s “Approve / Deny / Query” submission.
        """
        requisition = get_object_or_404(Requisition, pk=pk)

        if not request.user.has_perm('supplychain.approve_requisition'):
            messages.error(request, "You do not have permission to approve requisitions.")
            return redirect('supplychain:requisition-detail', pk=pk)

        if requisition.status != Requisition.PENDING:
            messages.warning(request, "This requisition has already been processed.")
            return redirect('supplychain:requisition-detail', pk=pk)

        form = RequisitionApprovalForm(request.POST)
        if form.is_valid():
            # Save the approval action
            form.save(requisition=requisition, approver=request.user)
            messages.success(request, f"Requisition #{requisition.id} marked {requisition.status.lower()}.")

            # If approved, trigger PO creation (see next section)
            if requisition.status == Requisition.APPROVED:
                # We can call a helper function or rely on a signal to auto-generate the PO.
                generate_po_for_requisition(requisition, created_by=request.user)

            return redirect('supplychain:requisition-detail', pk=pk)
        else:
            # If form is invalid, re-render with errors
            context = {
                'requisition': requisition,
                'items': requisition.items.select_related('product').all(),
                'approvals': requisition.approvals.select_related('approver').order_by('-timestamp'),
                'approval_form': form,
                'can_approve': True,
            }
            return render(request, 'supplychain/requisitions/detail.html', context)
