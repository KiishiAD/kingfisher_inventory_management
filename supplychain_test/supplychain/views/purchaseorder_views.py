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
    PurchaseOrderItemFormSet,
    PurchaseOrderFilterForm)

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
        qs = (
            PurchaseOrder.objects
            .all()
            .select_related('supplier', 'requisition', 'created_by')
            .order_by('-created_at')
        )

        # 2) Bind the filter form to GET params (?purchaser=..., ?supplier=..., etc.)
        self.filter_form = PurchaseOrderFilterForm(self.request.GET or None)

        # 3) If the form validates, pull cleaned data and apply .filter() calls
        if self.filter_form.is_valid():
            purchaser = self.filter_form.cleaned_data.get("purchaser")
            supplier = self.filter_form.cleaned_data.get("supplier")
            start_date = self.filter_form.cleaned_data.get("start_date")
            end_date = self.filter_form.cleaned_data.get("end_date")
            status = self.filter_form.cleaned_data.get("status")

            # I'm assuming PurchaseOrder has a ForeignKey to the user called created_by.
            # If your field is called purchaser instead, change to qs.filter(purchaser=purchaser)
            if purchaser:
                qs = qs.filter(created_by=purchaser)

            if supplier:
                qs = qs.filter(supplier=supplier)

            if start_date:
                qs = qs.filter(created_at__date__gte=start_date)

            if end_date:
                qs = qs.filter(created_at__date__lte=end_date)

            if status:
                qs = qs.filter(status=status)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['section'] = 'purchase_orders'

        context['filter_form'] = getattr(
            self, 'filter_form', PurchaseOrderFilterForm()
        )

        if hasattr(self, "filter_form") and self.filter_form.is_valid():
            active_status = self.filter_form.cleaned_data.get("status") or ""
        else:
            active_status = ""

        context["status_choices"] = PurchaseOrder.STATUS_CHOICES
        context["active_status"] = active_status

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
            # ↓ add unified workflow audit trail
            'timeline': build_workitem_timeline_for_po(po),
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
        # Base: only pending for COO
        qs = (
            PurchaseOrder.objects
            .filter(status=PurchaseOrder.PENDING_COO)
            .select_related('supplier', 'requisition', 'created_by')
            .order_by('created_at')
        )

        self.filter_form = PurchaseOrderFilterForm(self.request.GET or None)

        if self.filter_form.is_valid():
            purchaser = self.filter_form.cleaned_data.get("purchaser")
            supplier = self.filter_form.cleaned_data.get("supplier")
            start_date = self.filter_form.cleaned_data.get("start_date")
            end_date = self.filter_form.cleaned_data.get("end_date")

            if purchaser:
                qs = qs.filter(created_by=purchaser)

            if supplier:
                qs = qs.filter(supplier=supplier)

            if start_date:
                qs = qs.filter(created_at__date__gte=start_date)

            if end_date:
                qs = qs.filter(created_at__date__lte=end_date)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['section'] = 'purchase_orders'
        context['filter_form'] = getattr(
            self, 'filter_form', PurchaseOrderFilterForm()
        )
        return context