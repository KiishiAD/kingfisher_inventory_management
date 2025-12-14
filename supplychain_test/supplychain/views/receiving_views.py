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
    ReceivingAmendmentNotesForm,
)
from ..models import Receiving
from ..utils import build_workitem_timeline_for_po


class ReceivingListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    List receivings for anyone involved in the workflow:
    - receiving entry users
    - accounting reviewers
    - COO amend users
    """
    model = Receiving
    template_name = "supplychain/receiving/list.html"
    context_object_name = "receivings"
    paginate_by = 20
    raise_exception = True  # prevents redirect loops

    def has_permission(self):
        u = self.request.user
        return (
            u.has_perm("supplychain.record_receiving")
            or u.has_perm("supplychain.review_receiving")
            or u.has_perm("supplychain.amend_receiving")
        )

    def get_queryset(self):
        qs = (
            Receiving.objects
            .select_related("purchase_order", "purchase_order__supplier", "received_by")
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
    Single page supports 4 modes:
      - entry (PENDING + record_receiving)
      - accounting_review (UNDER_REVIEW + review_receiving)
      - coo_amend (QUERIED + amend_receiving)
      - readonly (everyone else)
    """
    raise_exception = True  # prevents redirect loops

    def has_permission(self):
        u = self.request.user
        return (
            u.has_perm("supplychain.record_receiving")
            or u.has_perm("supplychain.review_receiving")
            or u.has_perm("supplychain.amend_receiving")
        )

    def get_object(self, pk):
        return get_object_or_404(
            Receiving.objects.select_related(
                "purchase_order",
                "purchase_order__supplier",
                "received_by",
            ).prefetch_related(
                "items__po_item__product",
            ),
            pk=pk,
        )

    def _get_mode(self, request, receiving):
        if receiving.status == Receiving.PENDING and request.user.has_perm("supplychain.record_receiving"):
            return "entry"
        if receiving.status == Receiving.UNDER_REVIEW and request.user.has_perm("supplychain.review_receiving"):
            return "accounting_review"
        if receiving.status == Receiving.QUERIED and request.user.has_perm("supplychain.amend_receiving"):
            return "coo_amend"
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

    def _build_receiving_audit(self, receiving):
        events = []

        events.append({
            "timestamp": getattr(receiving, "created_at", None),
            "who": None,
            "label": f"Receiving #{receiving.id} created",
            "details": f"Status: {receiving.get_status_display()}",
        })

        if receiving.received_at:
            events.append({
                "timestamp": receiving.received_at,
                "who": receiving.received_by,
                "label": "Receiving recorded",
                "details": "Quantities captured and sent to accounting review.",
            })

        if receiving.status == Receiving.QUERIED:
            queried = receiving.items.filter(accounting_queried=True).select_related("po_item__product")
            lines = []
            for ri in queried:
                p = ri.po_item.product
                pname = getattr(p, "name", str(p))
                note = (ri.accounting_notes or "").strip()
                if note:
                    lines.append(f"- {pname}: {note}")
                else:
                    lines.append(f"- {pname}")
            details = "Queried lines:\n" + ("\n".join(lines) if lines else "- (none selected)")
            events.append({
                "timestamp": getattr(receiving, "reviewed_at", None) or getattr(receiving, "updated_at", None),
                "who": getattr(receiving, "reviewed_by", None),
                "label": "Accounting queried receiving",
                "details": details,
            })

        if receiving.status == Receiving.REVIWED:
            details = (getattr(receiving, "review_notes", "") or "").strip()
            events.append({
                "timestamp": getattr(receiving, "reviewed_at", None) or getattr(receiving, "updated_at", None),
                "who": getattr(receiving, "reviewed_by", None),
                "label": "Accounting cleared receiving for payment",
                "details": details,
            })

        if getattr(receiving, "amended_at", None):
            details = (getattr(receiving, "amendment_notes", "") or "").strip()
            events.append({
                "timestamp": receiving.amended_at,
                "who": getattr(receiving, "amended_by", None),
                "label": "COO amended receiving",
                "details": details,
            })

        events = [e for e in events if e.get("timestamp")]
        events.sort(key=lambda e: e["timestamp"])
        return events

    def get(self, request, pk):
        receiving = self.get_object(pk)
        po = receiving.purchase_order
        mode = self._get_mode(request, receiving)

        header_form = None
        item_formset = None
        accounting_formset = None
        review_form = None
        amend_form = None

        if mode in ("entry", "coo_amend"):
            header_form = ReceivingHeaderForm(instance=receiving)
            item_formset = ReceivingItemFormSet(instance=receiving)

        elif mode == "accounting_review":
            accounting_formset = ReceivingAccountingItemFormSet(instance=receiving)
            for f in accounting_formset.forms:
                self._annotate_variance_obj(f.instance)

            review_form = ReceivingReviewNotesForm(
                initial={"review_notes": (getattr(receiving, "review_notes", "") or "")}
            )

        receiving_items = self._annotate_variance_list(receiving) if mode == "readonly" else None

      
        context = {
        "section": "receiving",
        "mode": mode,
        "receiving": receiving,
        "purchase_order": po,
        "header_form": header_form,
        "item_formset": item_formset,
        "accounting_formset": accounting_formset,
        "review_form": review_form,
        "coo_form": coo_form,              # NEW (below)
        "receiving_items": receiving_items, # use for readonly + COO view
        "timeline": build_workitem_timeline_for_po(po),  # single source of truth
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
                context = {
                    "section": "receiving",
                    "mode": mode,
                    "receiving": receiving,
                    "purchase_order": po,
                    "header_form": header_form,
                    "item_formset": item_formset,
                    "timeline": build_workitem_timeline_for_po(po),
                    "receiving_audit": self._build_receiving_audit(receiving),
                }
                return render(request, "supplychain/receiving/detail.html", context)

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

        # COO AMEND (amend_receiving)
        if mode == "coo_amend":
            header_form = ReceivingHeaderForm(request.POST, request.FILES, instance=receiving)
            item_formset = ReceivingItemFormSet(request.POST, instance=receiving)
            amend_form = ReceivingAmendmentNotesForm(request.POST)

            if not (header_form.is_valid() and item_formset.is_valid() and amend_form.is_valid()):
                context = {
                    "section": "receiving",
                    "mode": mode,
                    "receiving": receiving,
                    "purchase_order": po,
                    "header_form": header_form,
                    "item_formset": item_formset,
                    "amend_form": amend_form,
                    "timeline": build_workitem_timeline_for_po(po),
                    "receiving_audit": self._build_receiving_audit(receiving),
                }
                return render(request, "supplychain/receiving/detail.html", context)

            with transaction.atomic():
                rec = header_form.save(commit=False)

                # optional audit fields (only if they exist on your model)
                if hasattr(rec, "amended_by"):
                    rec.amended_by = request.user
                if hasattr(rec, "amended_at"):
                    rec.amended_at = timezone.now()
                if hasattr(rec, "amendment_notes"):
                    rec.amendment_notes = amend_form.cleaned_data.get("amendment_notes", "").strip()

                rec.status = Receiving.UNDER_REVIEW
                rec.save()

                item_formset.instance = rec
                item_formset.save()

            messages.success(request, "Amendments submitted and returned to accounting review.")
            return redirect("supplychain:receiving-detail", pk=receiving.pk)

        # ACCOUNTING REVIEW (review_receiving)
        if mode == "accounting_review":
            accounting_formset = ReceivingAccountingItemFormSet(request.POST, instance=receiving)
            review_form = ReceivingReviewNotesForm(request.POST)

            if not (accounting_formset.is_valid() and review_form.is_valid()):
                for f in accounting_formset.forms:
                    self._annotate_variance_obj(f.instance)

                context = {
                    "section": "receiving",
                    "mode": mode,
                    "receiving": receiving,
                    "purchase_order": po,
                    "accounting_formset": accounting_formset,
                    "review_form": review_form,
                    "timeline": build_workitem_timeline_for_po(po),
                    "receiving_audit": self._build_receiving_audit(receiving),
                }
                return render(request, "supplychain/receiving/detail.html", context)

            with transaction.atomic():
                accounting_formset.save()

                # overall review note (only if your model has it)
                if hasattr(receiving, "review_notes"):
                    receiving.review_notes = review_form.cleaned_data.get("review_notes", "").strip()

                if hasattr(receiving, "reviewed_by"):
                    receiving.reviewed_by = request.user
                if hasattr(receiving, "reviewed_at"):
                    receiving.reviewed_at = timezone.now()

                any_missing_qty = receiving.items.filter(actual_quantity__isnull=True).exists()
                any_line_queried = receiving.items.filter(accounting_queried=True).exists()

                if any_missing_qty or any_line_queried:
                    receiving.status = Receiving.QUERIED
                    receiving.save()
                    if any_missing_qty and not any_line_queried:
                        messages.warning(
                            request,
                            "Some quantities are missing, so this receiving was marked as queried.",
                        )
                    else:
                        messages.warning(request, "Receiving queried and sent to COO for amendment.")
                else:
                    receiving.status = Receiving.REVIWED
                    receiving.save()
                    messages.success(request, "Receiving reviewed and cleared for payment.")

            return redirect("supplychain:receiving-detail", pk=receiving.pk)

        # READONLY
        messages.info(request, "This receiving is not editable at your current stage/permission.")
        return redirect("supplychain:receiving-detail", pk=receiving.pk)
