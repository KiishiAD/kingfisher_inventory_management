from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import TemplateView, CreateView, ListView, DetailView, FormView
from django.urls import reverse_lazy
from django.contrib import messages
from django.views import View
from django.db import transaction
from ..utils import *
from ..models import Receiving
from django.utils import timezone
from ..forms import ReceivingHeaderForm, ReceivingItemFormSet


class ReceivingListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    List receivings.

    Similar to PurchaseOrderListView, but focused on Receiving records.
    Each line shows:
      - Receiving id
      - Linked PO and supplier
      - Status
      - Summary of items (for pending, this is effectively 'awaited items')
      - Invoice present or not
    """
    model = Receiving
    template_name = 'supplychain/receiving/list.html'
    context_object_name = 'receivings'
    permission_required = 'supplychain.record_receiving'
    paginate_by = 20

    def get_queryset(self):
        qs = (
            Receiving.objects
            .select_related('purchase_order', 'purchase_order__supplier', 'received_by')
            .prefetch_related('items__po_item__product')
            .order_by('-created_at')
        )

        # If you later add a filter form (status, supplier, dates),
        # you can mirror PurchaseOrderFilterForm logic here.
        # For now, we list all receivings.
        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['section'] = 'receiving'
        context['status_choices'] = Receiving.STATUS_CHOICES
        context['active_status'] = self.request.GET.get("status", "")
        return context

    def handle_no_permission(self):
        messages.error(self.request, "You do not have permission to view receivings.")
        return super().handle_no_permission()



class ReceivingDetailView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "supplychain.record_receiving"

    def get_object(self, pk):
        return get_object_or_404(
            Receiving.objects.select_related(
                "purchase_order",
                "purchase_order__supplier",
            ).prefetch_related(
                "items__po_item__product",
            ),
            pk=pk,
        )

    def _annotate_variance(self, receiving):
        """
        Attach variance_text and variance_css to each ReceivingItem
        for use in the read-only template.
        """
        items = list(
            receiving.items.select_related("po_item__product").all()
        )

        for ri in items:
            po_qty = ri.po_item.quantity or Decimal("0")
            actual = ri.actual_quantity

            if actual is None:
                ri.variance_text = "Not recorded yet"
                ri.variance_css = "text-muted"
                continue

            diff = Decimal(actual) - po_qty
            abs_diff = abs(diff)

            if diff == 0:
                ri.variance_text = "Supplied amount matches PO"
                ri.variance_css = "text-success"
            elif diff < 0:
                ri.variance_text = f"Undersupplied by {abs_diff:.2f}"
                ri.variance_css = "text-danger"
            else:
                ri.variance_text = f"Oversupplied by {abs_diff:.2f}"
                ri.variance_css = "text-primary"

        return items


    def get(self, request, pk):
        receiving = self.get_object(pk)
        po = receiving.purchase_order
        is_editable = (receiving.status == Receiving.PENDING)

        header_form = ReceivingHeaderForm(instance=receiving) if is_editable else None
        item_formset = ReceivingItemFormSet(instance=receiving) if is_editable else None

        receiving_items = self._annotate_variance(receiving)

        context = {
            "receiving": receiving,
            "purchase_order": po,
            "header_form": header_form,
            "item_formset": item_formset,
            "receiving_items": receiving_items,
            "section": "receiving",
            "is_editable": is_editable,
        }
        return render(request, "supplychain/receiving/detail.html", context)

    def post(self, request, pk):
        receiving = self.get_object(pk)

        if receiving.status != Receiving.PENDING:
            messages.error(
                request,
                "This receiving is no longer editable at the receiving stage."
            )
            return redirect("supplychain:receiving-detail", pk=pk)

        header_form = ReceivingHeaderForm(
            request.POST,
            request.FILES,
            instance=receiving,
        )
        item_formset = ReceivingItemFormSet(
            request.POST,
            instance=receiving,
        )

        if not (header_form.is_valid() and item_formset.is_valid()):
            receiving_items = self._annotate_variance(receiving)
            context = {
                "receiving": receiving,
                "purchase_order": receiving.purchase_order,
                "header_form": header_form,
                "item_formset": item_formset,
                "receiving_items": receiving_items,
                "section": "receiving",
                "is_editable": True,
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

        messages.success(
            request,
            "Receiving recorded successfully and sent for accounting review."
        )
        return redirect("supplychain:receiving-detail", pk=pk)