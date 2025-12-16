# supplychain/views/payment_views.py

from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import (
    Sum, F, Count, DecimalField, ExpressionWrapper
)
from django.db.models.functions import Coalesce
from django.views.generic import ListView

from ..models import Payment


class PaymentsListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Payment
    template_name = "supplychain/payments/list.html"
    context_object_name = "payments"
    paginate_by = 20
    raise_exception = True

    def has_permission(self):
        return self.request.user.has_perm("supplychain.process_payment")

    def get_queryset(self):
        line_total = ExpressionWrapper(
            F("purchase_order__items__quantity") * F("purchase_order__items__unit_cost"),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )

        qs = (
            Payment.objects
            .select_related(
                "purchase_order",
                "purchase_order__supplier",
                "created_by",
                "processed_by",
            )
            .annotate(
                po_total=Coalesce(Sum(line_total), Decimal("0.00")),
                item_count=Coalesce(Count("purchase_order__items", distinct=True), 0),
            )
            .order_by("-created_at")
        )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["section"] = "payments"
        ctx["status_choices"] = Payment.STATUS_CHOICES

        # Default filter on page load = Pending
        ctx["active_status"] = self.request.GET.get("status", Payment.PENDING)
        return ctx
