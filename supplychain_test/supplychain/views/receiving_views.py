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


class ReceivingListView(LoginRequiredMixin, TemplateView):
    """Placeholder view for goods received notes."""
    template_name = 'supplychain/receiving/list.html'
    model= Receiving
    template_name = 'supplychain/receiving/list.html'
    permission_required = 'supplychain.record_receiving'
    paginate_by = 20

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['section'] = 'receiving'
        context['receivings'] = Receiving.objects.all().order_by('-received_at')
        return context





class ReceivingDetailView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Three-way check page (first step: recording what was received).

    - Shows Purchase Order lines (read-only).
    - Allows user with 'record_receiving' to:
      - Update actual quantities for each item,
      - Upload supplier invoice (image/PDF).
    """
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

    def get(self, request, pk):
        receiving = self.get_object(pk)
        po = receiving.purchase_order

        header_form = ReceivingHeaderForm(instance=receiving)
        item_formset = ReceivingItemFormSet(instance=receiving)

        context = {
            "receiving": receiving,
            "purchase_order": po,
            "header_form": header_form,
            "item_formset": item_formset,
            "section": "receiving",
        }
        return render(request, "supplychain/receiving/detail.html", context)

    def post(self, request, pk):
        """
        Handle the receiving submission:
        - Save actual quantities
        - Save invoice file
        - Set received_by / received_at
        - Move status from PENDING -> UNDER_REVIEW
        """
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
            # re-render with errors
            context = {
                "receiving": receiving,
                "purchase_order": receiving.purchase_order,
                "header_form": header_form,
                "item_formset": item_formset,
                "section": "receiving",
            }
            return render(request, "supplychain/receiving/detail.html", context)

        with transaction.atomic():
            # Save header (invoice file)
            receiving = header_form.save(commit=False)
            if receiving.received_by is None:
                receiving.received_by = request.user
            if receiving.received_at is None:
                receiving.received_at = timezone.now()

            # Move status to UNDER_REVIEW (ready for accounting)
            receiving.status = Receiving.UNDER_REVIEW
            receiving.save()

            # Save items (actual quantities)
            item_formset.instance = receiving
            item_formset.save()

        messages.success(request, "Receiving recorded successfully and sent for accounting review.")
        return redirect("supplychain:receiving-detail", pk=pk)