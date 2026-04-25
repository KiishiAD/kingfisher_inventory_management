# supplychain/views/inventory_views.py

from decimal import Decimal

from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import (
    Sum, Case, When, F, DecimalField, Value,
    OuterRef, Subquery, DateTimeField
)
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from ..models import Product, StockTransaction, LowStockAlert, Category


# ----------------------------
# Filters / Forms
# ----------------------------

class InventoryFilterForm(forms.Form):
    q = forms.CharField(required=False)
    category = forms.IntegerField(required=False)   # Category.id (Product.categories is M2M)
    below = forms.BooleanField(required=False)


class InventoryMovementFilterForm(forms.Form):
    start = forms.DateField(required=False)
    end = forms.DateField(required=False)
    category = forms.IntegerField(required=False)   # Category.id
    q = forms.CharField(required=False)

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start")
        end = cleaned.get("end")
        if start and end and start > end:
            self.add_error("end", "End date must be after start date.")
        return cleaned


# ----------------------------
# Helpers
# ----------------------------

DEC_OUT = DecimalField(max_digits=12, decimal_places=2)
DEC0 = Value(Decimal("0.00"), output_field=DEC_OUT)


def _signed_qty_expr(prefix: str = "stock_transactions__") -> Case:
    """
    Signed quantity mapping:
      RECEIVE    = +qty
      ISSUE      = -qty
      ADJUST_IN  = +qty
      ADJUST_OUT = -qty
    """
    return Case(
        When(**{f"{prefix}transaction_type": StockTransaction.RECEIVE}, then=F(f"{prefix}quantity")),
        When(**{f"{prefix}transaction_type": StockTransaction.ISSUE}, then=-F(f"{prefix}quantity")),
        When(**{f"{prefix}transaction_type": StockTransaction.ADJUST_IN}, then=F(f"{prefix}quantity")),
        When(**{f"{prefix}transaction_type": StockTransaction.ADJUST_OUT}, then=-F(f"{prefix}quantity")),
        default=DEC0,
        output_field=DEC_OUT,
    )


def _coalesce_decimal(expr):
    """
    Coalesce any decimal aggregation/expression to Decimal(0.00) with explicit output_field.
    Fixes: "Expression contains mixed types: DecimalField, IntegerField"
    """
    return Coalesce(expr, DEC0, output_field=DEC_OUT)


def _last_movement_subquery():
    return Subquery(
        StockTransaction.objects
        .filter(product_id=OuterRef("pk"))
        .order_by("-created_at")
        .values("created_at")[:1],
        output_field=DateTimeField(),
    )


def _signed_case_for_txn_queryset() -> Case:
    """
    Same mapping as _signed_qty_expr, but for StockTransaction queryset annotations.
    """
    return Case(
        When(transaction_type=StockTransaction.RECEIVE, then=F("quantity")),
        When(transaction_type=StockTransaction.ISSUE, then=-F("quantity")),
        When(transaction_type=StockTransaction.ADJUST_IN, then=F("quantity")),
        When(transaction_type=StockTransaction.ADJUST_OUT, then=-F("quantity")),
        default=DEC0,
        output_field=DEC_OUT,
    )


# ----------------------------
# Views
# ----------------------------

class InventoryListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    Inventory list:
    - Server-side pagination (paginate_by)
    - Client-side filtering like PO list (CURRENT PAGE ONLY)
    """
    model = Product
    template_name = "supplychain/inventory/list.html"
    context_object_name = "products"
    paginate_by = 50
    permission_required = "supplychain.view_inventory"  # adjust if needed

    def get_queryset(self):
        qs = (
            Product.objects
            .all()
            .select_related("uom")         
            .prefetch_related("categories") # existing
        )

        signed_qty = _signed_qty_expr(prefix="stock_transactions__")

        qs = qs.annotate(
            on_hand=_coalesce_decimal(Sum(signed_qty, output_field=DEC_OUT)),
            last_movement_at=_last_movement_subquery(),
        ).order_by("name")

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["section"] = "inventory"
        ctx["categories"] = Category.objects.all().order_by("name")
        ctx["active_low_stock_count"] = LowStockAlert.objects.filter(acknowledged=False).count()
        ctx["filter_form"] = InventoryFilterForm(self.request.GET or None)
        return ctx


class LowStockDashboardView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Active alerts only (acknowledged=False) + current on-hand.
    Includes product.uom + product.categories for display.
    """
    permission_required = "supplychain.view_inventory"

    def _active_alerts_with_quantities(self):
        alerts = list(
            LowStockAlert.objects
            .filter(acknowledged=False)
            .select_related("product", "product__uom")
            .prefetch_related("product__categories", "product__vendors")
            .order_by("acknowledged", "-triggered_at")
        )

        product_ids = [a.product_id for a in alerts]
        signed = _signed_case_for_txn_queryset()

        on_hand_rows = (
            StockTransaction.objects
            .filter(product_id__in=product_ids)
            .values("product_id")
            .annotate(qty=_coalesce_decimal(Sum(signed, output_field=DEC_OUT)))
        )
        on_hand_map = {row["product_id"]: row["qty"] for row in on_hand_rows}

        for alert in alerts:
            current = on_hand_map.get(alert.product_id, Decimal("0.00"))
            alert.current_on_hand = current
            alert.reorder_gap = max(alert.threshold - current, Decimal("0.00"))
            alert.reorder_value = alert.reorder_gap * alert.product.unit_cost

        return alerts

    def get(self, request):
        alerts = self._active_alerts_with_quantities()
        out_of_stock_count = sum(1 for alert in alerts if alert.current_on_hand <= 0)
        below_threshold_count = len(alerts) - out_of_stock_count
        estimated_reorder_value = sum((alert.reorder_value for alert in alerts), Decimal("0.00"))

        return render(request, "supplychain/inventory/low_stock.html", {
            "section": "inventory",
            "alerts": alerts,
            "total_alerts": len(alerts),
            "out_of_stock_count": out_of_stock_count,
            "below_threshold_count": below_threshold_count,
            "estimated_reorder_value": estimated_reorder_value,
            "can_acknowledge_lowstock": request.user.has_perm("supplychain.acknowledge_lowstock"),
        })

    def post(self, request):
        if not request.user.has_perm("supplychain.acknowledge_lowstock"):
            raise PermissionDenied

        alert = get_object_or_404(
            LowStockAlert.objects.select_related("product"),
            pk=request.POST.get("alert_id"),
            acknowledged=False,
        )
        alert.acknowledged = True
        alert.acknowledged_by = request.user
        alert.acknowledged_at = timezone.now()
        alert.save(update_fields=["acknowledged", "acknowledged_by", "acknowledged_at", "updated_at"])
        messages.success(request, f"Acknowledged low-stock alert for {alert.product.name}.")
        return redirect("supplychain:inventory-low-stock")


class InventoryDetailView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Per-product inventory ledger + on-hand + active alert.
    """
    permission_required = "supplychain.view_inventory"

    def get(self, request, pk: int):
        product = get_object_or_404(
            Product.objects
            .select_related("uom")          # ✅ add this
            .prefetch_related("categories"),
            pk=pk,
        )

        signed = _signed_case_for_txn_queryset()

        on_hand = (
            StockTransaction.objects
            .filter(product=product)
            .aggregate(qty=_coalesce_decimal(Sum(signed, output_field=DEC_OUT)))
        )["qty"] or Decimal("0.00")

        last_movement_at = (
            StockTransaction.objects
            .filter(product=product)
            .order_by("-created_at")
            .values_list("created_at", flat=True)
            .first()
        )

        txns_qs = (
            product.stock_transactions
            .select_related("created_by")
            .order_by("-created_at")
        )

        paginator = Paginator(txns_qs, 50)
        page_obj = paginator.get_page(request.GET.get("page"))

        active_alert = (
            product.low_stock_alerts
            .filter(acknowledged=False)
            .order_by("-triggered_at")
            .first()
        )

        # keep existing query params when paging
        qd = request.GET.copy()
        qd.pop("page", None)
        qs_no_page = qd.urlencode()

        return render(request, "supplychain/inventory/detail.html", {
            "section": "inventory",
            "product": product,
            "on_hand": on_hand,
            "active_alert": active_alert,
            "page_obj": page_obj,
            "last_movement_at": last_movement_at,
            "qs_no_page": qs_no_page,
        })


class InventoryMovementReportView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Analytics by date range.
    Filters: start, end, category (Category.id), q (product name contains)
    """
    permission_required = "supplychain.view_inventory"

    def get(self, request):
        form = InventoryMovementFilterForm(request.GET)
        form.is_valid()

        start = form.cleaned_data.get("start")
        end = form.cleaned_data.get("end")
        q = (form.cleaned_data.get("q") or "").strip()
        cat_id = form.cleaned_data.get("category")

        txns = StockTransaction.objects.select_related("product")

        if start:
            txns = txns.filter(created_at__date__gte=start)
        if end:
            txns = txns.filter(created_at__date__lte=end)
        if q:
            txns = txns.filter(product__name__icontains=q)
        if cat_id:
            txns = txns.filter(product__categories__id=cat_id)  # M2M filter

        # received/issued as positive measures
        received_expr = Case(
            When(transaction_type=StockTransaction.RECEIVE, then=F("quantity")),
            default=DEC0,
            output_field=DEC_OUT,
        )
        issued_expr = Case(
            When(transaction_type=StockTransaction.ISSUE, then=F("quantity")),
            default=DEC0,
            output_field=DEC_OUT,
        )

        # net as signed measure
        net_expr = Case(
            When(transaction_type=StockTransaction.RECEIVE, then=F("quantity")),
            When(transaction_type=StockTransaction.ISSUE, then=-F("quantity")),
            When(transaction_type=StockTransaction.ADJUST_IN, then=F("quantity")),
            When(transaction_type=StockTransaction.ADJUST_OUT, then=-F("quantity")),
            default=DEC0,
            output_field=DEC_OUT,
        )

        per_product = (
            txns.values("product_id", "product__name")
            .annotate(
                received=_coalesce_decimal(Sum(received_expr, output_field=DEC_OUT)),
                issued=_coalesce_decimal(Sum(issued_expr, output_field=DEC_OUT)),
                net=_coalesce_decimal(Sum(net_expr, output_field=DEC_OUT)),
            )
            .order_by("product__name")
        )

        top_issued = (
            txns.values("product_id", "product__name")
            .annotate(issued=_coalesce_decimal(Sum(issued_expr, output_field=DEC_OUT)))
            .order_by("-issued")[:20]
        )

        return render(request, "supplychain/inventory/movement_report.html", {
            "section": "inventory",
            "form": form,
            "per_product": per_product,
            "top_issued": top_issued,
            "categories": Category.objects.all().order_by("name"),
        })
