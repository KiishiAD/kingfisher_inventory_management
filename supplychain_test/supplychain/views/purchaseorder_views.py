from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView, TemplateView,CreateView, ListView, View
from django.urls import reverse_lazy
from django.contrib import messages
from django.views import View
from django.db import transaction
from decimal import Decimal

from ..models.master_data import Product
from ..models import (
    PurchaseOrder,
    PurchaseOrderItem, 
    PurchaseOrderApproval, 
    Requisition, 
    RequisitionApproval)

from ..forms import (
    RequisitionFilterForm,
    PurchaseOrderApprovalForm, 
    PurchaseOrderForm, 
    PurchaseOrderItemFormSet)

from django.contrib import messages
from django.db import transaction
from ..utils import build_workitem_timeline_for_po

class PurchaseOrderListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """List purchase orders (all created purchase orders)."""
    model = PurchaseOrder
    template_name = 'supplychain/purchase_orders/list.html'
    context_object_name = 'purchase_orders'
    permission_required = 'supplychain.create_purchaseorder'
    paginate_by = 20

    def get_queryset(self):
        return PurchaseOrder.objects.all().order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['section'] = 'purchase_orders'
        return context


class PurchaseOrderDetailView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'supplychain.create_purchaseorder'

    def get(self, request, pk):
        po = get_object_or_404(PurchaseOrder, pk=pk)
        can_approve = request.user.has_perm('supplychain.approve_purchaseorder')

        items = po.items.select_related('product').all()

        total_amount = sum(
            (item.line_total for item in items),
            Decimal("0")
        )

        context = {
            'purchase_order': po,
            'items': items,
            'approvals': po.approvals.select_related('approver').order_by('timestamp'),
            'can_approve': can_approve,
            'section': 'purchase_orders',
            'po_total_amount': total_amount,
        }
        return render(request, 'supplychain/purchase_orders/detail.html', context)
    

class PurchaseOrderCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """
    Create a new Purchase Order.

    - If requisition is set, it must be an APPROVED requisition with no existing PO.
    - If requisition is left blank, this is a pure manual PO.
    """
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = 'supplychain/purchase_orders/create.html'
    permission_required = 'supplychain.create_purchaseorder'
    success_url = reverse_lazy('supplychain:po-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['section'] = 'purchase_orders'

        if self.request.POST:
            context['item_formset'] = PurchaseOrderItemFormSet(self.request.POST)
        else:
            context['item_formset'] = PurchaseOrderItemFormSet()

        # For JS: unit_cost + UOM per product
        context['products'] = Product.objects.select_related('uom').all()
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        item_formset = context['item_formset']

        if not item_formset.is_valid():
            # inline formset errors get shown together with the main form
            return self.render_to_response(self.get_context_data(form=form))

        requisition = form.cleaned_data.get('requisition')

        # Business rule: if linking to a requisition, it must not already have a PO
        if requisition is not None:
            # Because PurchaseOrder.requisition is OneToOne, we can use hasattr:
            if hasattr(requisition, 'purchase_order'):
                form.add_error(
                    'requisition',
                    "This requisition already has a purchase order."
                )
                return self.render_to_response(self.get_context_data(form=form))

        with transaction.atomic():
            self.object = form.save(commit=False)
            self.object.created_by = self.request.user
            self.object.status = PurchaseOrder.PENDING_COO
            self.object.save()

            item_formset.instance = self.object

    # Force unit_cost from the selected product, ignore user input
            for f in item_formset.forms:
                if not f.cleaned_data:
                    continue
                if f.cleaned_data.get('DELETE'):
                    continue
                product = f.cleaned_data.get('product')
                if product:
                    f.instance.unit_cost = product.unit_cost

            item_formset.save()

        messages.success(
            self.request,
            f"PO #{self.object.id} created and sent for COO approval."
        )
        return redirect(self.success_url)

    def handle_no_permission(self):
        messages.error(self.request, "You do not have permission to create purchase orders.")
        return super().handle_no_permission()
    

class PurchaseOrderPendingListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    Purchase orders awaiting COO approval.
    """
    model = PurchaseOrder
    template_name = 'supplychain/purchase_orders/pending.html'
    context_object_name = 'pending_purchase_orders'
    permission_required = 'supplychain.approve_purchaseorder'
    paginate_by = 20

    def get_queryset(self):
        return (
            PurchaseOrder.objects
            .filter(status=PurchaseOrder.PENDING_COO)
            .select_related('supplier', 'requisition', 'created_by')
            .order_by('created_at')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['section'] = 'purchase_orders'
        return context
