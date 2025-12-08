from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView, TemplateView,CreateView, ListView, View, UpdateView
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
from ..utils import build_workitem_timeline_for_po, generate_receiving_for_purchase_order
import logging

logger = logging.getLogger(__name__)

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
        context["created_by"] = PurchaseOrder.created_by

        return context


class PurchaseOrderDetailView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Detail + COO approval in one view.

    - GET: show PO details, items, approvals, and (if user can approve) the approval form.
    - POST: process COO decision (Approve / Deny / Query) and write audit trail.
    """
    permission_required = "supplychain.create_purchaseorder"

    def get_object(self, pk):
        return get_object_or_404(
            PurchaseOrder.objects.select_related("supplier", "requisition", "created_by"),
            pk=pk,
        )

    def get(self, request, pk):
        po = self.get_object(pk)

        items = po.items.select_related("product").all()
        total_amount = sum((item.line_total for item in items), Decimal("0"))

        can_approve = (
            request.user.has_perm("supplychain.approve_purchaseorder")
            and po.status == PurchaseOrder.PENDING_COO
        )

        approval_form = PurchaseOrderApprovalForm() if can_approve else None

        context = {
            "purchase_order": po,
            "items": items,
            "approvals": po.approvals.select_related("approver").order_by("timestamp"),
            "can_approve": can_approve,
            "approval_form": approval_form,
            "section": "purchase_orders",
            "po_total_amount": total_amount,
            "timeline": build_workitem_timeline_for_po(po),
        }
        return render(request, "supplychain/purchase_orders/detail.html", context)

    def post(self, request, pk):
        """
        Handle COO approval decision submission (Approve / Deny / Query).
        """
        po = self.get_object(pk)

        # 1) Permission check: only users with approve_purchaseorder may approve
        if not request.user.has_perm("supplychain.approve_purchaseorder"):
            messages.error(request, "You do not have permission to approve purchase orders.")
            return redirect("supplychain:po-detail", pk=po.pk)

        # 2) Status check: only allow action when PO is in pending COO state
        if po.status != PurchaseOrder.PENDING_COO:
            messages.warning(request, "This purchase order has already been processed.")
            return redirect("supplychain:po-detail", pk=po.pk)

        form = PurchaseOrderApprovalForm(request.POST)

        if not form.is_valid():
            # Re-render detail view with the bound form + errors
            items = po.items.select_related("product").all()
            total_amount = sum((item.line_total for item in items), Decimal("0"))
            context = {
                "purchase_order": po,
                "items": items,
                "approvals": po.approvals.select_related("approver").order_by("timestamp"),
                "can_approve": True,
                "approval_form": form,
                "section": "purchase_orders",
                "po_total_amount": total_amount,
                "timeline": build_workitem_timeline_for_po(po),
            }
            return render(request, "supplychain/purchase_orders/detail.html", context)

        action = form.cleaned_data["action"]

        try:
            with transaction.atomic():
                # 3) Update PO status (APPROVED / DENIED / QUERIED)
                po.status = action
                # If TimeStampedModel has updated_at, it will auto-update on save
                po.save(update_fields=["status", "updated_at"])

                # 4) Create PurchaseOrderApproval audit record
                form.save(purchase_order=po, approver=request.user)

                # 5) OPTIONAL: schedule notification email after commit (commented out for now)
                #
                # def _notify():
                #     try:
                #         from ..services.notifications.email_notifications import (
                #             notify_purchase_order_approved_to_all,
                #             notify_purchase_order_denied_to_all,
                #             notify_purchase_order_queried_to_all,
                #         )
                #
                #         if po.status == PurchaseOrder.APPROVED:
                #             notify_purchase_order_approved_to_all(po)
                #         elif po.status == PurchaseOrder.DENIED:
                #             notify_purchase_order_denied_to_all(po)
                #         elif po.status == PurchaseOrder.QUERIED:
                #             notify_purchase_order_queried_to_all(po)
                #     except Exception:
                #         logger.exception("Error sending notification for purchase order #%s", po.id)
                #
                # transaction.on_commit(_notify)

                if po.status == PurchaseOrder.APPROVED:
                    generate_receiving_for_purchase_order(po)

            messages.success(
                request,
                f"Purchase Order #{po.id} marked {po.status.lower()}.",
            )

        except ValueError as exc:
            # In case you later raise ValueError from business rules
            messages.error(request, str(exc))

        return redirect("supplychain:po-detail", pk=po.pk)

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


class PurchaseOrderUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """
    Allow the PO creator to edit a QUERIED purchase order and resubmit
    it back to PENDING_COO, mirroring RequisitionUpdateView.
    """
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = "supplychain/purchase_orders/update.html"
    permission_required = "supplychain.create_purchaseorder"  # <- this was missing
    success_url = reverse_lazy("supplychain:po-list")

    def get_queryset(self):
        # Only allow the creator to edit, and only when status is QUERIED
        return PurchaseOrder.objects.filter(
            created_by=self.request.user,
            status=PurchaseOrder.QUERIED,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["section"] = "purchase_orders"

        item_formset = kwargs.get("item_formset")
        if item_formset is not None:
            context["item_formset"] = item_formset
        else:
            if self.request.POST:
                context["item_formset"] = PurchaseOrderItemFormSet(
                    self.request.POST,
                    instance=self.object,
                )
            else:
                context["item_formset"] = PurchaseOrderItemFormSet(
                    instance=self.object,
                )

        context["approvals"] = (
            self.object.approvals
            .select_related("approver")
            .order_by("timestamp")
        )
        context["timeline"] = build_workitem_timeline_for_po(self.object)

        items = self.object.items.select_related("product").all()
        context["po_total_amount"] = sum(
            (item.line_total for item in items),
            Decimal("0"),
        )

        context["products"] = Product.objects.select_related("uom").all()

        return context

    def form_valid(self, form):
        context = self.get_context_data()
        item_formset = context["item_formset"]

        if not item_formset.is_valid():
            return self.render_to_response(
                self.get_context_data(form=form, item_formset=item_formset)
            )

        with transaction.atomic():
            # Save header changes
            self.object = form.save()

            item_formset.instance = self.object

            # Auto-calc unit_cost from product (same as create view)
            for f in item_formset.forms:
                if not f.cleaned_data:
                    continue
                if f.cleaned_data.get("DELETE"):
                    continue
                product = f.cleaned_data.get("product")
                if product:
                    f.instance.unit_cost = product.unit_cost

            item_formset.save()

            # Reset status back to PENDING_COO for re-approval
            self.object.status = PurchaseOrder.PENDING_COO
            self.object.save(update_fields=["status", "updated_at"])

            PurchaseOrderApproval.objects.create(
                purchase_order=self.object,
                approver=self.request.user,
                action=PurchaseOrder.PENDING_COO,
                notes="PO updated and resubmitted for COO approval.",
            )

        messages.success(
            self.request,
            f"Purchase Order #{self.object.id} updated and resubmitted for approval.",
        )
        return redirect(self.success_url)

    def handle_no_permission(self):
        messages.error(self.request, "You do not have permission to update purchase orders.")
        return super().handle_no_permission()
