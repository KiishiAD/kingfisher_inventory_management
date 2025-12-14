# supplychain/views/receiving_views.py

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from ..forms import (
    ReceivingHeaderForm,
    ReceivingItemFormSet,
    ReceivingAccountingItemFormSet,
    ReceivingReviewNotesForm,
)
from ..models import Receiving
from ..utils import build_workitem_timeline_for_po


class ReceivingListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Receiving
    template_name = "supplychain/receiving/list.html"
    context_object_name = "receivings"
    paginate_by = 20
    raise_exception = True

    def has_permission(self):
        u = self.request.user
        return (
            u.has_perm("supplychain.record_receiving")
            or u.has_perm("supplychain.review_receiving")
            or u.has_perm("supplychain.approve_receiving")
        )

    def get_queryset(self):
        qs = (
            Receiving.objects
            .select_related(
                "purchase_order",
                "purchase_order__supplier",
                "received_by",
                "reviewed_by",
                "sent_to_coo_by",
                "coo_decision_by",
            )
            .prefetch_related("items__po_item__product")
            .order_by("-created_at")
        )

        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["section"] = "receiving"
        context["status_choices"] = Receiving.STATUS_CHOICES
        context["active_status"] = self.request.GET.get("status", "")
        return context


class ReceivingDetailView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Modes:
      - entry:           status=PENDING and record_receiving
      - accounting:      status=UNDER_REVIEW, not yet sent_to_coo, and review_receiving
      - coo_approval:    sent_to_coo_at set, coo_decision_at not set, and approve_receiving
      - readonly:        everyone else
    """
    raise_exception = True

    def has_permission(self):
        u = self.request.user
        return (
            u.has_perm("supplychain.record_receiving")
            or u.has_perm("supplychain.review_receiving")
            or u.has_perm("supplychain.approve_receiving")
        )

    def get_object(self, pk):
        return get_object_or_404(
            Receiving.objects.select_related(
                "purchase_order",
                "purchase_order__supplier",
                "received_by",
                "reviewed_by",
                "sent_to_coo_by",
                "coo_decision_by",
            ).prefetch_related(
                "items__po_item__product",
            ),
            pk=pk,
        )

    def _is_pending_coo(self, receiving) -> bool:
        return bool(getattr(receiving, "sent_to_coo_at", None)) and not bool(getattr(receiving, "coo_decision_at", None))

    def _get_mode(self, request, receiving):
        u = request.user

        if receiving.status == Receiving.PENDING and u.has_perm("supplychain.record_receiving"):
            return "entry"

        if self._is_pending_coo(receiving) and u.has_perm("supplychain.approve_receiving"):
            return "coo_approval"

        # Accounting can only act while it's UNDER_REVIEW AND not already sent to COO
        if (
            receiving.status == Receiving.UNDER_REVIEW
            and (not self._is_pending_coo(receiving))
            and u.has_perm("supplychain.review_receiving")
        ):
            return "accounting_review"

        return "readonly"

    def _annotate_variance_obj(self, ri):
        tol = Decimal("0.50")

        po_qty = (ri.po_item.quantity or Decimal("0"))
        actual = ri.actual_quantity

        if actual is None:
            ri.variance_text = "Not recorded yet"
            ri.variance_css = "text-muted"
            return ri

        diff = Decimal(actual) - po_qty
        abs_diff = abs(diff)

        if diff == 0:
            ri.variance_text = "Supplied amount matches PO"
            ri.variance_css = "text-success"
        elif abs_diff <= tol:
            if diff > 0:
                ri.variance_text = f"Slightly oversupplied by {abs_diff:.2f} (within 0.50)"
            else:
                ri.variance_text = f"Slightly undersupplied by {abs_diff:.2f} (within 0.50)"
            ri.variance_css = "text-success"
        elif diff > tol:
            ri.variance_text = f"Oversupplied by {abs_diff:.2f}"
            ri.variance_css = "text-danger"
        else:
            ri.variance_text = f"Undersupplied by {abs_diff:.2f}"
            ri.variance_css = "text-primary"

        return ri

    def _annotate_variance_list(self, receiving):
        items = list(receiving.items.select_related("po_item__product").all())
        for ri in items:
            self._annotate_variance_obj(ri)
        return items

    def _requires_coo_approval(self, receiving) -> bool:
        """
        COO approval required if ANY line is oversupplied by > 0.50.
        Undersupply or exact match never requires COO approval.
        """
        tol = Decimal("0.50")
        for ri in receiving.items.select_related("po_item").all():
            if ri.actual_quantity is None:
                continue
            po_qty = ri.po_item.quantity or Decimal("0")
            diff = Decimal(ri.actual_quantity) - po_qty
            if diff > tol:
                return True
        return False

    def get(self, request, pk):
        receiving = self.get_object(pk)
        po = receiving.purchase_order
        mode = self._get_mode(request, receiving)

        header_form = None
        item_formset = None
        accounting_formset = None
        review_form = None
        receiving_items = None

        requires_coo = self._requires_coo_approval(receiving)

        if mode == "entry":
            header_form = ReceivingHeaderForm(instance=receiving)
            item_formset = ReceivingItemFormSet(instance=receiving)

        elif mode == "accounting_review":
            accounting_formset = ReceivingAccountingItemFormSet(instance=receiving)
            for f in accounting_formset.forms:
                self._annotate_variance_obj(f.instance)

            review_form = ReceivingReviewNotesForm(
                initial={"review_notes": (getattr(receiving, "review_notes", "") or "")}
            )

        else:
            # COO + readonly both show read-only receiving lines with variance
            receiving_items = self._annotate_variance_list(receiving)

        context = {
            "section": "receiving",
            "mode": mode,
            "receiving": receiving,
            "purchase_order": po,
            "header_form": header_form,
            "item_formset": item_formset,
            "accounting_formset": accounting_formset,
            "review_form": review_form,
            "receiving_items": receiving_items,
            "requires_coo": requires_coo,
            "is_pending_coo": self._is_pending_coo(receiving),
            "timeline": build_workitem_timeline_for_po(po),  # single audit trail
        }
        return render(request, "supplychain/receiving/detail.html", context)

    def post(self, request, pk):
        receiving = self.get_object(pk)
        po = receiving.purchase_order
        mode = self._get_mode(request, receiving)

        # ENTRY (record_receiving)
        if mode == "entry":
            header_form = ReceivingHeaderForm(request.POST, request.FILES, instance=receiving)
            item_formset = ReceivingItemFormSet(request.POST, instance=receiving)

            if not (header_form.is_valid() and item_formset.is_valid()):
                return render(request, "supplychain/receiving/detail.html", {
                    "section": "receiving",
                    "mode": mode,
                    "receiving": receiving,
                    "purchase_order": po,
                    "header_form": header_form,
                    "item_formset": item_formset,
                    "timeline": build_workitem_timeline_for_po(po),
                    "requires_coo": self._requires_coo_approval(receiving),
                    "is_pending_coo": self._is_pending_coo(receiving),
                })

            with transaction.atomic():
                rec = header_form.save(commit=False)

                if rec.received_by is None:
                    rec.received_by = request.user
                if rec.received_at is None:
                    rec.received_at = timezone.now()

                rec.status = Receiving.UNDER_REVIEW
                rec.save()

                item_formset.instance = rec
                item_formset.save()

            messages.success(request, "Receiving recorded and sent for accounting review.")
            return redirect("supplychain:receiving-detail", pk=receiving.pk)

        # ACCOUNTING REVIEW (review_receiving)
        if mode == "accounting_review":
            accounting_action = (request.POST.get("accounting_action") or "").strip().upper()
            allowed = {"APPROVE", "DENY", "SEND_COO"}

            accounting_formset = ReceivingAccountingItemFormSet(request.POST, instance=receiving)
            review_form = ReceivingReviewNotesForm(request.POST)

            if accounting_action not in allowed:
                # render with validation feedback
                for f in accounting_formset.forms:
                    self._annotate_variance_obj(f.instance)

                messages.error(request, "Select Approve, Deny, or Send for COO approval before submitting.")
                return render(request, "supplychain/receiving/detail.html", {
                    "section": "receiving",
                    "mode": mode,
                    "receiving": receiving,
                    "purchase_order": po,
                    "accounting_formset": accounting_formset,
                    "review_form": review_form,
                    "timeline": build_workitem_timeline_for_po(po),
                    "requires_coo": self._requires_coo_approval(receiving),
                    "is_pending_coo": self._is_pending_coo(receiving),
                })

            if not (accounting_formset.is_valid() and review_form.is_valid()):
                for f in accounting_formset.forms:
                    self._annotate_variance_obj(f.instance)

                return render(request, "supplychain/receiving/detail.html", {
                    "section": "receiving",
                    "mode": mode,
                    "receiving": receiving,
                    "purchase_order": po,
                    "accounting_formset": accounting_formset,
                    "review_form": review_form,
                    "timeline": build_workitem_timeline_for_po(po),
                    "requires_coo": self._requires_coo_approval(receiving),
                    "is_pending_coo": self._is_pending_coo(receiving),
                })

            # Guard (legacy rows)
            if receiving.items.filter(actual_quantity__isnull=True).exists():
                for f in accounting_formset.forms:
                    self._annotate_variance_obj(f.instance)

                messages.error(request, "Some lines have no actual quantity recorded. Receiving must be completed first.")
                return render(request, "supplychain/receiving/detail.html", {
                    "section": "receiving",
                    "mode": mode,
                    "receiving": receiving,
                    "purchase_order": po,
                    "accounting_formset": accounting_formset,
                    "review_form": review_form,
                    "timeline": build_workitem_timeline_for_po(po),
                    "requires_coo": self._requires_coo_approval(receiving),
                    "is_pending_coo": self._is_pending_coo(receiving),
                })

            with transaction.atomic():
                accounting_formset.save()

                receiving.review_notes = review_form.cleaned_data.get("review_notes", "").strip()
                receiving.reviewed_by = request.user
                receiving.reviewed_at = timezone.now()

                # DENY: immediate final denial
                if accounting_action == "DENY":
                    receiving.status = getattr(Receiving, "DENIED", "DENIED")
                    receiving.save()
                    messages.error(request, "Accounting denied this receiving.")
                    return redirect("supplychain:receiving-detail", pk=receiving.pk)

                # SEND_COO: manual send, status stays UNDER_REVIEW
                if accounting_action == "SEND_COO":
                    if self._is_pending_coo(receiving):
                        receiving.save()
                        messages.info(request, "Already sent to COO and awaiting decision.")
                        return redirect("supplychain:receiving-detail", pk=receiving.pk)

                    receiving.sent_to_coo_by = request.user
                    receiving.sent_to_coo_at = timezone.now()
                    receiving.save()
                    messages.warning(request, "Sent to COO for approval/denial (status remains Pending Accounting Review).")
                    return redirect("supplychain:receiving-detail", pk=receiving.pk)

                # APPROVE:
                # - if oversupply > 0.50 exists => send to COO (status remains UNDER_REVIEW)
                # - else => clear for payment
                if self._requires_coo_approval(receiving):
                    if not self._is_pending_coo(receiving):
                        receiving.sent_to_coo_by = request.user
                        receiving.sent_to_coo_at = timezone.now()
                    receiving.save()
                    messages.warning(request, "Oversupply above 0.50 detected. Sent to COO for approval/denial.")
                else:
                    receiving.status = Receiving.REVIWED
                    receiving.save()
                    messages.success(request, "Accounting approved. Cleared for payment.")

            return redirect("supplychain:receiving-detail", pk=receiving.pk)

        # COO APPROVAL (approve_receiving) — only when sent_to_coo_at set, status still UNDER_REVIEW
        if mode == "coo_approval":
            coo_action = (request.POST.get("coo_action") or "").strip().upper()
            allowed = {"APPROVE", "DENY"}
            coo_notes = (request.POST.get("coo_notes") or "").strip()

            if coo_action not in allowed:
                receiving_items = self._annotate_variance_list(receiving)
                messages.error(request, "Select Approve or Deny before submitting.")
                return render(request, "supplychain/receiving/detail.html", {
                    "section": "receiving",
                    "mode": mode,
                    "receiving": receiving,
                    "purchase_order": po,
                    "receiving_items": receiving_items,
                    "timeline": build_workitem_timeline_for_po(po),
                    "requires_coo": self._requires_coo_approval(receiving),
                    "is_pending_coo": self._is_pending_coo(receiving),
                })

            with transaction.atomic():
                receiving.coo_decision_by = request.user
                receiving.coo_decision_at = timezone.now()
                receiving.coo_decision_notes = coo_notes

                if coo_action == "APPROVE":
                    receiving.status = Receiving.REVIWED
                    receiving.save()
                    messages.success(request, "COO approved. Cleared for payment.")
                else:
                    receiving.status = getattr(Receiving, "DENIED", "DENIED")
                    receiving.save()
                    messages.error(request, "COO denied this receiving.")

            return redirect("supplychain:receiving-detail", pk=receiving.pk)

        messages.info(request, "This receiving is not editable at your current stage/permission.")
        return redirect("supplychain:receiving-detail", pk=receiving.pk)
