# supplychain/views/payment_views.py

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from ..models import Payment, Receiving
from ..forms import PaymentProcessForm
from ..utils import build_workitem_timeline_for_po


class PaymentsListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Payment
    template_name = "supplychain/payments/list.html"
    context_object_name = "payments"
    paginate_by = 20
    raise_exception = True
    permission_required = "supplychain.process_payment"

    def get_queryset(self):
        qs = (
            Payment.objects
            .select_related("purchase_order", "purchase_order__supplier", "processed_by")
            .prefetch_related(
                "purchase_order__items",
                "purchase_order__items__product",
                Prefetch(
                    "purchase_order__receivings",
                    queryset=Receiving.objects.only("id", "purchase_order_id", "supplier_invoice"),
                    to_attr="prefetched_receivings",
                ),
            )
            .order_by("-created_at")
        )

        status = self.request.GET.get("status")
        if status:
            qs = qs.filter(status=status)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["section"] = "payments"
        context["status_choices"] = Payment.STATUS_CHOICES
        context["active_status"] = self.request.GET.get("status", "")

        # Attach computed fields used by the template
        for p in context["payments"]:
            po = p.purchase_order
            items = list(po.items.all())
            p.item_count = len(items)
            p.po_total = sum((i.line_total for i in items), Decimal("0"))

            receivings = getattr(po, "prefetched_receivings", [])
            receiving = receivings[0] if receivings else None
            p.receiving_id = receiving.id if receiving else None

        return context


class PaymentDetailView(LoginRequiredMixin, PermissionRequiredMixin, View):
    raise_exception = True
    permission_required = "supplychain.process_payment"

    def get_object(self, pk):
        return get_object_or_404(
            Payment.objects.select_related(
                "purchase_order",
                "purchase_order__supplier",
                "processed_by",
                "created_by",
            ).prefetch_related(
                "purchase_order__items",
                "purchase_order__items__product",
            ),
            pk=pk,
        )

    def get(self, request, pk):
        payment = self.get_object(pk)
        po = payment.purchase_order

        receiving = (
            Receiving.objects
            .select_related("purchase_order")
            .filter(purchase_order=po)
            .first()
        )

        po_items = list(po.items.all())
        po_total = sum((i.line_total for i in po_items), Decimal("0"))

        form = None
        if payment.status == Payment.PENDING:
            form = PaymentProcessForm(instance=payment)

        context = {
            "section": "payments",
            "payment": payment,
            "purchase_order": po,
            "receiving": receiving,
            "po_items": po_items,
            "po_total": po_total,
            "form": form,
            "timeline": build_workitem_timeline_for_po(po),
        }
        return render(request, "supplychain/payments/detail.html", context)

    def post(self, request, pk):
        payment = self.get_object(pk)
        po = payment.purchase_order

        if payment.status != Payment.PENDING:
            messages.info(request, "This payment is already processed and cannot be edited.")
            return redirect("supplychain:payment-detail", pk=payment.pk)

        form = PaymentProcessForm(request.POST, request.FILES, instance=payment)
        receiving = Receiving.objects.filter(purchase_order=po).first()
        po_items = list(po.items.all())
        po_total = sum((i.line_total for i in po_items), Decimal("0"))

        if not form.is_valid():
            return render(request, "supplychain/payments/detail.html", {
                "section": "payments",
                "payment": payment,
                "purchase_order": po,
                "receiving": receiving,
                "po_items": po_items,
                "po_total": po_total,
                "form": form,
                "timeline": build_workitem_timeline_for_po(po),
            })

        with transaction.atomic():
            p = form.save(commit=False)
            p.status = Payment.PROCESSED
            p.processed_by = request.user
            p.processed_at = timezone.now()
            p.save()

        messages.success(request, "Payment processed.")
        return redirect("supplychain:payment-detail", pk=payment.pk)
