# utils.py

from decimal import Decimal
from collections import defaultdict

from django.db import transaction
from django.db.models import Case, When, F, DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from ..models import (
    Product,            
    LowStockAlert,
    StockTransaction,
    Receiving,
    Requisition,
    Destination,
)

DEC_OUT = DecimalField(max_digits=12, decimal_places=2)
DEC0 = Value(Decimal("0.00"), output_field=DEC_OUT)


def _signed_qty_case_for_stock() -> Case:
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


def on_hand(product_id: int) -> Decimal:
    signed = _signed_qty_case_for_stock()
    agg = StockTransaction.objects.filter(product_id=product_id).aggregate(
        qty=Coalesce(Sum(signed, output_field=DEC_OUT), DEC0, output_field=DEC_OUT)
    )
    return agg["qty"] or Decimal("0.00")


def evaluate_low_stock(product_id: int) -> None:
    """
    Creates/maintains a LowStockAlert when on_hand < product.low_stock_threshold.
    Resolves the active alert when stock recovers.
    """
    p = Product.objects.only("id", "low_stock_threshold").get(pk=product_id)
    threshold = p.low_stock_threshold

    # If you allow null thresholds, treat as "no alerting"
    if threshold is None:
        return

    qty = on_hand(product_id)

    active = (
        LowStockAlert.objects
        .filter(product_id=product_id, resolved_at__isnull=True)
        .order_by("-triggered_at")
        .first()
    )

    if qty < threshold:
        if not active:
            LowStockAlert.objects.create(product_id=product_id, threshold=threshold)
        else:
            # keep snapshot aligned if threshold changed while alert is active
            if active.threshold != threshold:
                active.threshold = threshold
                active.save(update_fields=["threshold"])
    else:
        if active:
            active.resolved_at = timezone.now()
            active.save(update_fields=["resolved_at"])


def record_receiving_as_stock(receiving_id: int, actor_id: int | None = None) -> None:
    receiving = (
        Receiving.objects
        .select_related("purchase_order")
        .prefetch_related("items__po_item__product")
        .get(pk=receiving_id)
    )

    # Only count stock when it is cleared for payment (your rule)
    if receiving.status != Receiving.REVIWED:
        return

    totals = defaultdict(Decimal)
    for ri in receiving.items.all():
        if ri.actual_quantity is None:
            continue
        totals[ri.po_item.product_id] += Decimal(ri.actual_quantity)

    for product_id, qty in totals.items():
        StockTransaction.objects.get_or_create(
            product_id=product_id,
            transaction_type=StockTransaction.RECEIVE,
            source_type=StockTransaction.SRC_RECEIVING,
            source_id=receiving_id,
            defaults={
                "quantity": qty,
                "created_by_id": actor_id,
                "note": f"Receiving #{receiving_id} cleared for payment",
            },
        )
        evaluate_low_stock(product_id)


def record_store_requisition_issue(requisition_id: int, actor_id: int | None = None) -> None:
    req = (
        Requisition.objects
        .select_related("destination")
        .prefetch_related("items__product")
        .get(pk=requisition_id)
    )

    # Only ISSUE when requisition is approved AND destination is STORE (your rule)
    if req.status != Requisition.APPROVED:
        return
    if req.destination.name != Destination.STORE:
        return

    totals = defaultdict(Decimal)
    for item in req.items.all():
        totals[item.product_id] += Decimal(item.quantity)

    for product_id, qty in totals.items():
        StockTransaction.objects.get_or_create(
            product_id=product_id,
            transaction_type=StockTransaction.ISSUE,
            source_type=StockTransaction.SRC_REQUISITION,
            source_id=requisition_id,
            defaults={
                "quantity": qty,
                "created_by_id": actor_id,
                "note": f"Store requisition #{requisition_id} approved",
            },
        )
        evaluate_low_stock(product_id)
