# supplychain/views/requisition_views.py

from collections import defaultdict
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.db.models import Sum, Case, When, F, DecimalField, Value
from django.db.models.functions import Coalesce
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView

import logging

from ..models import (
    Requisition,
    RequisitionApproval,
    Destination,
    StockTransaction,   # ✅ needed to check inventory at request time
)
from ..forms import (
    RequisitionForm,
    RequisitionItemFormSet,
    RequisitionApprovalForm,
    RequisitionFilterForm,
)
from ..utils import generate_po_for_requisition, build_workitem_timeline, record_store_requisition_issue

logger = logging.getLogger(__name__)

DEC_OUT = DecimalField(max_digits=12, decimal_places=2)
DEC0 = Value(Decimal("0.00"), output_field=DEC_OUT)


def _signed_case_for_stock():
    """
    Signed quantity mapping:
      RECEIVE    = +qty
      ISSUE      = -qty
      ADJUST_IN  = +qty
      ADJUST_OUT = -qty
    """
    return Case(
        When(transaction_type=StockTransaction.RECEIVE, then=F("quantity")),
        When(transaction_type=StockTransaction.ISSUE, then=-F("quantity")),
        When(transaction_type=StockTransaction.ADJUST_IN, then=F("quantity")),
        When(transaction_type=StockTransaction.ADJUST_OUT, then=-F("quantity")),
        default=DEC0,
        output_field=DEC_OUT,
    )


def _on_hand_map(product_ids: list[int]) -> dict[int, Decimal]:
    """
    Returns {product_id: on_hand} for the given products.
    """
    if not product_ids:
        return {}

    signed = _signed_case_for_stock()
    rows = (
        StockTransaction.objects
        .filter(product_id__in=product_ids)
        .values("product_id")
        .annotate(qty=Coalesce(Sum(signed, output_field=DEC_OUT), DEC0, output_field=DEC_OUT))
    )
    out = {r["product_id"]: (r["qty"] or Decimal("0.00")) for r in rows}

    # ensure every id exists in map
    for pid in product_ids:
        out.setdefault(pid, Decimal("0.00"))
    return out


def _validate_store_stock(item_formset) -> None:
    """
    Adds form errors if destination is STORE and:
    - a product has 0 on-hand (out of stock), OR
    - requested quantity exceeds on-hand.

    This is called AFTER item_formset.is_valid() so cleaned_data is available.
    """
    requested_totals = defaultdict(Decimal)
    line_products = []  # keep per-line references for better per-line errors

    for f in item_formset.forms:
        if not getattr(f, "cleaned_data", None) or f.cleaned_data.get("DELETE"):
            continue
        product = f.cleaned_data.get("product")
        qty = f.cleaned_data.get("quantity")

        if not product or qty is None:
            continue

        qty = Decimal(qty)
        requested_totals[product.id] += qty
        line_products.append((f, product.id, qty, product))

    product_ids = list(requested_totals.keys())
    stock = _on_hand_map(product_ids)

    # 1) Hard rule: if stock is 0, block requesting it (your requirement)
    # 2) Also block if requesting more than available (prevents negative stock)
    for f, pid, line_qty, product in line_products:
        available = stock.get(pid, Decimal("0.00"))

        if available <= 0:
            f.add_error("product", f"Out of stock (available: {available}).")
            continue

        total_requested_for_product = requested_totals[pid]
        if total_requested_for_product > available:
            # add the error to the quantity field so it’s obvious what to change
            f.add_error(
                "quantity",
                f"Not enough stock. Available: {available}. Requested (total): {total_requested_for_product}.",
            )


class RequisitionCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """View for a requester to create a new Requisition."""
    model = Requisition
    form_class = RequisitionForm
    template_name = "supplychain/requisitions/create.html"
    permission_required = "supplychain.submit_requisition"
    success_url = reverse_lazy("supplychain:requisition-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["section"] = "requisitions"

        item_formset = kwargs.get("item_formset")
        if item_formset is not None:
            context["item_formset"] = item_formset
        else:
            if self.request.POST:
                context["item_formset"] = RequisitionItemFormSet(self.request.POST)
            else:
                context["item_formset"] = RequisitionItemFormSet()

        return context

    def form_valid(self, form):
        context = self.get_context_data(form=form)
        item_formset = context["item_formset"]

        if not item_formset.is_valid():
            return self.render_to_response(context)

        destination = form.cleaned_data.get("destination")

        # RULE 1: if destination == STORE, supplier must be empty on each item
        if destination and destination.name == Destination.STORE:
            for f in item_formset.forms:
                if not f.cleaned_data or f.cleaned_data.get("DELETE"):
                    continue
                supplier = f.cleaned_data.get("supplier")
                if supplier:
                    f.add_error("supplier", "Supplier must be empty when destination is STORE.")

        # RULE 2 (your request): block STORE requisitions if stock is 0 / insufficient
        if destination and destination.name == Destination.STORE:
            _validate_store_stock(item_formset)

        if any(f.errors for f in item_formset.forms) or item_formset.non_form_errors():
            return self.render_to_response(self.get_context_data(form=form, item_formset=item_formset))

        with transaction.atomic():
            self.object = form.save()
            item_formset.instance = self.object
            item_formset.save()

            initial_note = (form.cleaned_data.get("notes") or "").strip()
            if initial_note:
                RequisitionApproval.objects.create(
                    requisition=self.object,
                    approver=self.request.user,
                    action=Requisition.PENDING,
                    notes=f"Requester note: {initial_note}",
                )

        messages.success(self.request, f"Requisition #{self.object.id} created successfully!")
        return redirect(self.success_url)

    def handle_no_permission(self):
        messages.error(self.request, "You do not have permission to submit requisitions.")
        return super().handle_no_permission()


class RequisitionUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """Allow requester to update a queried requisition and resubmit."""
    model = Requisition
    form_class = RequisitionForm
    template_name = "supplychain/requisitions/update.html"
    permission_required = "supplychain.submit_requisition"
    success_url = reverse_lazy("supplychain:requisition-list")

    def get_queryset(self):
        return Requisition.objects.filter(
            requester=self.request.user,
            status=Requisition.QUERIED,
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["section"] = "requisitions"

        item_formset = kwargs.get("item_formset")
        if item_formset is not None:
            context["item_formset"] = item_formset
        else:
            if self.request.POST:
                context["item_formset"] = RequisitionItemFormSet(
                    self.request.POST,
                    instance=self.object,
                )
            else:
                context["item_formset"] = RequisitionItemFormSet(instance=self.object)

        context["approvals"] = self.object.approvals.select_related("approver").order_by("timestamp")
        context["timeline"] = build_workitem_timeline(self.object)
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        logger.debug("RequisitionUpdateView POST keys: %s", list(request.POST.keys()))
        logger.debug("RequisitionUpdateView FILES keys: %s", list(request.FILES.keys()))
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        context = self.get_context_data()
        item_formset = context["item_formset"]

        if not item_formset.is_valid():
            return self.render_to_response(self.get_context_data(form=form, item_formset=item_formset))

        destination = form.cleaned_data.get("destination")

        # RULE 1: if destination == STORE, supplier must be empty on each item
        if destination and destination.name == Destination.STORE:
            for f in item_formset.forms:
                if not f.cleaned_data or f.cleaned_data.get("DELETE"):
                    continue
                supplier = f.cleaned_data.get("supplier")
                if supplier:
                    f.add_error("supplier", "Supplier must be empty when destination is STORE.")

        # RULE 2 (your request): block STORE requisitions if stock is 0 / insufficient
        if destination and destination.name == Destination.STORE:
            _validate_store_stock(item_formset)

        if any(f.errors for f in item_formset.forms) or item_formset.non_form_errors():
            return self.render_to_response(self.get_context_data(form=form, item_formset=item_formset))

        item_changes = []
        for f in item_formset.forms:
            if not f.has_changed():
                continue

            if f.instance.pk is None and not f.cleaned_data.get("DELETE", False):
                item_changes.append(f"Added {f.cleaned_data.get('product')} × {f.cleaned_data.get('quantity')}")
                continue

            if f.cleaned_data.get("DELETE", False):
                if f.instance.pk is not None:
                    item_changes.append(f"Removed {f.instance.product} × {f.instance.quantity}")
                continue

            line_bits = []
            if "product" in f.changed_data:
                line_bits.append(f"product: {f.instance.product} → {f.cleaned_data.get('product')}")
            if "quantity" in f.changed_data:
                line_bits.append(f"quantity: {f.instance.quantity} → {f.cleaned_data.get('quantity')}")
            if "supplier" in f.changed_data:
                line_bits.append(f"supplier: {f.instance.supplier} → {f.cleaned_data.get('supplier')}")

            if line_bits:
                item_changes.append(f"Updated item {f.instance.product}: " + "; ".join(line_bits))

        self.object = form.save()
        item_formset.instance = self.object
        item_formset.save()

        self.object.status = Requisition.PENDING
        self.object.save(update_fields=["status", "updated_at"])

        requester_reply = (form.cleaned_data.get("notes") or "").strip()
        note_parts = []
        if requester_reply:
            note_parts.append(f"Requester reply: {requester_reply}")
        if item_changes:
            note_parts.append("Changes: " + " | ".join(item_changes))
        if not note_parts:
            note_parts.append("Requisition updated")

        RequisitionApproval.objects.create(
            requisition=self.object,
            approver=self.request.user,
            action=Requisition.PENDING,
            notes="\n".join(note_parts),
        )

        messages.success(self.request, f"Requisition #{self.object.id} updated and resubmitted for approval.")
        return redirect(self.success_url)

    def handle_no_permission(self):
        messages.error(self.request, "You do not have permission to update requisitions.")
        return super().handle_no_permission()


class RequisitionListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """List all requisitions where the logged-in user is the requester."""
    model = Requisition
    template_name = "supplychain/requisitions/list.html"
    context_object_name = "requisitions"
    permission_required = "supplychain.submit_requisition"
    paginate_by = 20

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["section"] = "requisitions"
        return context

    def get_queryset(self):
        return Requisition.objects.filter(requester=self.request.user).order_by("-created_at")

    def handle_no_permission(self):
        messages.error(self.request, "You cannot view requisitions.")
        return super().handle_no_permission()


class RequisitionPendingListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """List requisitions, defaulting to status='PENDING'."""
    model = Requisition
    template_name = "supplychain/requisitions/pending.html"
    context_object_name = "pending_requisitions"
    permission_required = "supplychain.approve_requisition"
    paginate_by = 20
    form_class = RequisitionFilterForm

    def get_queryset(self):
        qs = Requisition.objects.select_related("requester", "destination").order_by("created_at")

        self.filter_form = self.form_class(self.request.GET or None)
        default_status = Requisition.PENDING

        if self.filter_form.is_valid():
            data = self.filter_form.cleaned_data
            status = data.get("status") or default_status
            qs = qs.filter(status=status)

            if data.get("requester"):
                qs = qs.filter(requester=data["requester"])
            if data.get("start_date"):
                qs = qs.filter(created_at__date__gte=data["start_date"])
            if data.get("end_date"):
                qs = qs.filter(created_at__date__lte=data["end_date"])
            if data.get("destination"):
                qs = qs.filter(destination=data["destination"])
            if data.get("urgent") == "yes":
                qs = qs.filter(urgent=True)
            elif data.get("urgent") == "no":
                qs = qs.filter(urgent=False)
        else:
            qs = qs.filter(status=default_status)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["section"] = "requisitions"
        context["filter_form"] = getattr(self, "filter_form", self.form_class())
        context["status_choices"] = Requisition.STATUS_CHOICES
        if hasattr(self, "filter_form") and self.filter_form.is_valid():
            context["active_status"] = self.filter_form.cleaned_data.get("status") or Requisition.PENDING
        else:
            context["active_status"] = Requisition.PENDING
        return context

    def handle_no_permission(self):
        messages.error(self.request, "You do not have permission to approve requisitions.")
        return super().handle_no_permission()


class RequisitionAllListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """List all requisitions regardless of requester with optional filtering."""
    model = Requisition
    template_name = "supplychain/requisitions/all.html"
    context_object_name = "requisitions"
    permission_required = "supplychain.view_all_requisitions"
    paginate_by = 20
    form_class = RequisitionFilterForm

    def get_queryset(self):
        qs = Requisition.objects.select_related("requester", "destination").order_by("-created_at")

        self.filter_form = self.form_class(self.request.GET or None)
        if self.filter_form.is_valid():
            data = self.filter_form.cleaned_data
            if data.get("requester"):
                qs = qs.filter(requester=data["requester"])
            if data.get("start_date"):
                qs = qs.filter(created_at__date__gte=data["start_date"])
            if data.get("end_date"):
                qs = qs.filter(created_at__date__lte=data["end_date"])
            if data.get("destination"):
                qs = qs.filter(destination=data["destination"])
            if data.get("urgent") == "yes":
                qs = qs.filter(urgent=True)
            elif data.get("urgent") == "no":
                qs = qs.filter(urgent=False)
            if data.get("status"):
                qs = qs.filter(status=data["status"])

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["section"] = "requisitions"
        context["filter_form"] = getattr(self, "filter_form", self.form_class())
        context["status_choices"] = Requisition.STATUS_CHOICES
        if hasattr(self, "filter_form") and self.filter_form.is_valid():
            context["active_status"] = self.filter_form.cleaned_data.get("status") or ""
        else:
            context["active_status"] = ""
        return context

    def handle_no_permission(self):
        messages.error(self.request, "You do not have permission to view all requisitions.")
        return super().handle_no_permission()


class RequisitionDetailView(LoginRequiredMixin, View):
    """Show requisition details and optionally approval form."""

    def _get_requisition(self, pk):
        qs = Requisition.objects.select_related(
            "requester",
            "destination",
            "supplier",
            "Supplier_destination_sub_category",
        )
        return get_object_or_404(qs, pk=pk)

    def _base_context(self, request, requisition, approval_form=None, can_approve=False):
        return {
            "requisition": requisition,
            "items": requisition.items.select_related("product").all(),
            "approvals": requisition.approvals.select_related("approver").order_by("timestamp"),
            "approval_form": approval_form,
            "can_approve": can_approve,
            "section": "requisitions",
            "timeline": build_workitem_timeline(requisition),
        }

    def get(self, request, pk):
        requisition = self._get_requisition(pk)

        if not (request.user == requisition.requester or request.user.has_perm("supplychain.approve_requisition")):
            messages.error(request, "You do not have permission to view this requisition.")
            return redirect("supplychain:requisition-list")

        can_approve = requisition.status == Requisition.PENDING and request.user.has_perm("supplychain.approve_requisition")
        approval_form = RequisitionApprovalForm() if can_approve else None

        context = self._base_context(request, requisition, approval_form=approval_form, can_approve=can_approve)
        return render(request, "supplychain/requisitions/detail.html", context)

    def post(self, request, pk):
        requisition = self._get_requisition(pk)

        if not request.user.has_perm("supplychain.approve_requisition"):
            messages.error(request, "You do not have permission to approve requisitions.")
            return redirect("supplychain:requisition-detail", pk=pk)

        if requisition.status != Requisition.PENDING:
            messages.warning(request, "This requisition has already been processed.")
            return redirect("supplychain:requisition-detail", pk=pk)

        form = RequisitionApprovalForm(request.POST)
        if not form.is_valid():
            context = self._base_context(request, requisition, approval_form=form, can_approve=True)
            return render(request, "supplychain/requisitions/detail.html", context)

        try:
            with transaction.atomic():
                # 1) Save the approval + set requisition status (your form.save does this)
                form.save(requisition=requisition, approver=request.user)

                # IMPORTANT: refresh local object inside the transaction so status is up-to-date
                requisition.refresh_from_db(fields=["status", "destination_id"])

                # 2) If approved, enforce the required side-effects
                if requisition.status == Requisition.APPROVED:
                    # PURCHASE => must create a PO
                    if requisition.destination.name == Destination.PURCHASE:
                        generate_po_for_requisition(requisition, created_by=request.user)

                        po_exists = PurchaseOrder.objects.filter(requisition=requisition).exists()
                        if not po_exists:
                            raise ValueError(
                                "Approval failed: a Purchase Order could not be created. Nothing was changed."
                            )

                    # STORE => must create inventory ISSUE transactions
                    if requisition.destination.name == Destination.STORE:
                        # run inside the transaction so failures rollback the approval
                        record_store_requisition_issue(requisition.pk, request.user.pk)

                        issued_exists = StockTransaction.objects.filter(
                            source_type=StockTransaction.SRC_REQUISITION,
                            source_id=requisition.pk,
                            transaction_type=StockTransaction.ISSUE,
                        ).exists()
                        if not issued_exists:
                            raise ValueError(
                                "Approval failed: stock could not be issued (inventory was not updated). Nothing was changed."
                            )

            messages.success(request, f"Requisition #{requisition.id} marked {requisition.status.lower()}.")

            # Notifications AFTER commit (safe to keep here)
            def _notify():
                try:
                    if requisition.status == Requisition.APPROVED:
                        from ..services.notifications.email_notifications import notify_requisition_approved_to_all
                        notify_requisition_approved_to_all(requisition)
                    elif requisition.status == Requisition.DENIED:
                        from ..services.notifications.email_notifications import notify_requisition_denied_to_all
                        notify_requisition_denied_to_all(requisition)
                except Exception:
                    logger.exception("Error sending notification for requisition #%s", requisition.id)

            transaction.on_commit(_notify)

        except ValueError as exc:
            messages.error(request, str(exc))

        return redirect("supplychain:requisition-detail", pk=pk)
