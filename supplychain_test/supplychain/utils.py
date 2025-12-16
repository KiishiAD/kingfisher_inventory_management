# supplychain/utils.py  (full file as per what you pasted, with payment timeline fixed)

from decimal import Decimal

from django.db import transaction

from .models import (
    PurchaseOrder,
    PurchaseOrderItem,
    Receiving,
    ReceivingItem,
    Payment,
)


def generate_po_for_requisition(requisition, created_by):
    """
    Create PurchaseOrder(s) from an approved requisition.

    Supports both shapes:
    - supplier on Requisition (single supplier)
    - supplier on RequisitionItem (multi supplier)

    Falls back to product.vendors.first() if needed.
    """
    existing = PurchaseOrder.objects.filter(requisition=requisition)
    if existing.exists():
        return existing[0] if existing.count() == 1 else list(existing)

    # Pull items (NO select_related('supplier') because supplier might not exist on the item anymore)
    items_qs = requisition.items.select_related("product").all()

    items_by_supplier = {}

    # Prefer a requisition-level supplier if present
    req_supplier = getattr(requisition, "supplier", None)

    for item in items_qs:
        supplier = None

        # 1) requisition-level supplier
        if req_supplier:
            supplier = req_supplier

        # 2) item-level supplier (only if field exists)
        if supplier is None and hasattr(item, "supplier_id"):
            supplier = getattr(item, "supplier", None)

        # 3) fallback to product vendors
        if supplier is None:
            vendors_qs = getattr(item.product, "vendors", None)
            supplier = vendors_qs.first() if vendors_qs is not None else None

        if supplier is None:
            raise ValueError(
                f"Cannot create PO: product {item.product!r} has no supplier/vendor"
            )

        items_by_supplier.setdefault(supplier, []).append(item)

    created_pos = []
    with transaction.atomic():
        for supplier, items in items_by_supplier.items():
            po = PurchaseOrder.objects.create(
                requisition=requisition,
                supplier=supplier,
                created_by=created_by,
                status=PurchaseOrder.PENDING_COO,
            )
            for item in items:
                PurchaseOrderItem.objects.create(
                    purchase_order=po,
                    product=item.product,
                    quantity=item.quantity,
                    unit_cost=getattr(item.product, "unit_cost", Decimal("0")),
                )
            created_pos.append(po)

    return created_pos[0] if len(created_pos) == 1 else created_pos


def generate_issuance_for_requisition(requisition, created_by):
    """Create an IssuanceRequest from an approved store requisition."""
    if hasattr(requisition, "issuance_request"):
        return requisition.issuance_request

    iss = IssuanceRequest.objects.create(
        requester=created_by,
        status=IssuanceRequest.PENDING,
    )
    for item in requisition.items.select_related("product").all():
        IssuanceItem.objects.create(
            issuance_request=iss,
            product=item.product,
            quantity=item.quantity,
        )
    return iss


def generate_receiving_for_purchase_order(purchase_order):
    existing = purchase_order.receivings.all()
    if existing.exists():
        return existing.first()

    with transaction.atomic():
        receiving = Receiving.objects.create(
            purchase_order=purchase_order,
            status=Receiving.PENDING,
        )
        for po_item in purchase_order.items.all():
            ReceivingItem.objects.create(
                receiving=receiving,
                po_item=po_item,
                actual_quantity=None,        # important: None means "Not recorded yet"
                flagged_for={},
                accounting_queried=False,
                accounting_notes="",
            )
    return receiving


def _payment_timeline_events(payment):
    """
    Timeline events for a Payment:
    - creation (pending)
    - processed (when processed_at set)
    """
    events = []

    # Created / pending
    created_ts = getattr(payment, "created_at", None)
    if created_ts:
        events.append({
            "timestamp": created_ts,
            "who": getattr(payment, "created_by", None),
            "label": f"Payment created ({payment.get_status_display()})",
            "details": "",
        })

    # Processed
    processed_ts = getattr(payment, "processed_at", None)
    if processed_ts:
        method = "—"
        try:
            method = payment.get_payment_type_display() if getattr(payment, "payment_type", None) else "—"
        except Exception:
            method = getattr(payment, "payment_type", None) or "—"

        notes = (getattr(payment, "payment_notes", "") or "").strip()

        events.append({
            "timestamp": processed_ts,
            "who": getattr(payment, "processed_by", None),
            "label": f"Payment processed ({method})",
            "details": notes,
        })

    return events


def build_workitem_timeline(requisition):
    """
    Unified workflow timeline rooted at a Requisition.
    """
    events = []

    # 1. Requisition created
    events.append({
        "timestamp": requisition.created_at,
        "who": requisition.requester,
        "label": f"Requisition #{requisition.id} created",
        "details": "",
    })

    # 2. Requisition approvals & conversations
    for a in requisition.approvals.select_related("approver").all():
        events.append({
            "timestamp": a.timestamp,
            "who": a.approver,
            "label": f"Requisition {a.action}",
            "details": a.notes,
        })

    # 3. Purchase orders linked to this requisition
    pos = (
        PurchaseOrder.objects
        .filter(requisition=requisition)
        .select_related("created_by", "supplier")
        .prefetch_related("approvals__approver")
    )

    for po in pos:
        events.append({
            "timestamp": po.created_at,
            "who": po.created_by,
            "label": f"PO #{po.id} created",
            "details": f"Supplier: {po.supplier}",
        })

        for a in po.approvals.all():
            events.append({
                "timestamp": a.timestamp,
                "who": a.approver,
                "label": f"PO {a.action}",
                "details": a.notes,
            })

        payment = getattr(po, "payment", None)
        if payment:
            events.extend(_payment_timeline_events(payment))

        # Optional: include receiving event if you want (safe, minimal)
        rec = po.receivings.order_by("created_at").first()
        if rec:
            events.extend(build_receiving_timeline_events(rec))

    # 4. Issuance (linked from requisition)
    issuance = getattr(requisition, "issuance_request", None)
    if issuance:
        events.append({
            "timestamp": issuance.created_at,
            "who": issuance.requester,
            "label": f"IssuanceRequest #{issuance.id} created",
            "details": "",
        })

    events = [e for e in events if e.get("timestamp")]
    events.sort(key=lambda e: e["timestamp"])
    return events


def build_workitem_timeline_for_po(po):
    """
    Unified workflow timeline starting from a PurchaseOrder.
    Includes:
      - PO creation + PO approvals
      - Payment created + Payment processed (if any)
      - Receiving incremental events
    """
    # If PO is linked to a requisition, reuse the requisition-rooted timeline
    if po.requisition_id:
        return build_workitem_timeline(po.requisition)

    events = [{
        "timestamp": po.created_at,
        "who": po.created_by,
        "label": f"PO #{po.id} created",
        "details": f"Supplier: {po.supplier}",
    }]

    for a in po.approvals.select_related("approver").all():
        events.append({
            "timestamp": a.timestamp,
            "who": a.approver,
            "label": f"PO {a.action}",
            "details": a.notes,
        })

    payment = getattr(po, "payment", None)
    if payment:
        events.extend(_payment_timeline_events(payment))

    # Receiving (append-only incremental events)
    rec = po.receivings.order_by("created_at").first()
    if rec:
        events.extend(build_receiving_timeline_events(rec))

    events = [e for e in events if e.get("timestamp")]
    events.sort(key=lambda e: e["timestamp"])
    return events


def build_receiving_timeline_events(receiving):
    """
    Incremental (append-only) receiving events based on timestamped audit fields.
    Avoids the "single event keeps changing" problem.
    """
    events = []

    # 1) Created
    events.append({
        "timestamp": getattr(receiving, "created_at", None),
        "who": None,
        "label": f"Receiving #{receiving.id} created",
        "details": "",
    })

    # 2) Goods recorded (entry submit)
    if getattr(receiving, "received_at", None):
        details_bits = []

        if getattr(receiving, "supplier_invoice", None):
            details_bits.append("Invoice uploaded.")
        else:
            details_bits.append("No invoice uploaded.")

        details_bits.append(_receiving_variance_details(receiving))

        events.append({
            "timestamp": receiving.received_at,
            "who": getattr(receiving, "received_by", None),
            "label": "Receiving recorded (goods received)",
            "details": "\n".join([b for b in details_bits if b]),
        })

    # 3) Accounting review (submitted)
    if getattr(receiving, "reviewed_at", None):
        status = getattr(receiving, "status", "")
        reviewed_value = getattr(type(receiving), "REVIWED", "REVIEWED")
        denied_value = getattr(type(receiving), "DENIED", "DENIED")

        sent_to_coo = bool(getattr(receiving, "sent_to_coo_at", None))

        if status == denied_value and not getattr(receiving, "coo_decision_at", None):
            label = "Receiving denied by accounting"
        elif status == reviewed_value and not sent_to_coo:
            label = "Receiving approved by accounting (cleared for payment)"
        elif sent_to_coo:
            label = "Receiving reviewed by accounting"
        else:
            label = "Receiving accounting review submitted"

        details_bits = []
        rn = (getattr(receiving, "review_notes", "") or "").strip()
        if rn:
            details_bits.append(rn)

        qd = _receiving_queried_lines_details(receiving)
        if qd:
            details_bits.append(qd)

        events.append({
            "timestamp": receiving.reviewed_at,
            "who": getattr(receiving, "reviewed_by", None),
            "label": label,
            "details": "\n".join(details_bits).strip(),
        })

    # 4) Sent to COO
    if getattr(receiving, "sent_to_coo_at", None):
        oversupply_lines = []
        tol = Decimal("0.50")
        for ri in receiving.items.select_related("po_item__product").all():
            if ri.actual_quantity is None:
                continue
            po_qty = ri.po_item.quantity or Decimal("0")
            diff = Decimal(ri.actual_quantity) - po_qty
            if diff > tol:
                product = getattr(ri.po_item.product, "name", str(ri.po_item.product))
                oversupply_lines.append(f"{product}: +{_fmt2(diff)}")

        details = ""
        if oversupply_lines:
            details = "Oversupply > 0.50:\n" + "\n".join(oversupply_lines[:6])
            if len(oversupply_lines) > 6:
                details += f"\n+ {len(oversupply_lines) - 6} more oversupply lines"

        events.append({
            "timestamp": receiving.sent_to_coo_at,
            "who": getattr(receiving, "sent_to_coo_by", None),
            "label": "Receiving sent to COO for approval/denial",
            "details": details,
        })

    # 5) COO decision
    if getattr(receiving, "coo_decision_at", None):
        status = getattr(receiving, "status", "")
        approved_value = getattr(type(receiving), "REVIWED", "REVIEWED")
        denied_value = getattr(type(receiving), "DENIED", "DENIED")

        if status == approved_value:
            label = "Receiving approved by COO (cleared for payment)"
        elif status == denied_value:
            label = "Receiving denied by COO"
        else:
            label = "Receiving COO decision recorded"

        details = (getattr(receiving, "coo_decision_notes", "") or "").strip()

        events.append({
            "timestamp": receiving.coo_decision_at,
            "who": getattr(receiving, "coo_decision_by", None),
            "label": label,
            "details": details,
        })

    events = [e for e in events if e.get("timestamp")]
    events.sort(key=lambda e: e["timestamp"])
    return events


def _fmt2(d):
    if d is None:
        return "—"
    try:
        return f"{Decimal(d):.2f}"
    except Exception:
        return str(d)


def _receiving_variance_details(receiving, max_lines=6, tol=Decimal("0.50")):
    """
    Returns a concise multi-line string describing what was recorded (and variances).
    This is a snapshot summary and works well for an append-only timeline.
    """
    rows = []
    mismatches = []

    items = list(receiving.items.select_related("po_item__product").all())

    for ri in items:
        po_qty = (ri.po_item.quantity or Decimal("0"))
        actual = ri.actual_quantity

        product = getattr(ri.po_item.product, "name", str(ri.po_item.product))

        if actual is None:
            mismatches.append(f"{product}: PO {_fmt2(po_qty)} → Received —")
            continue

        diff = Decimal(actual) - po_qty
        if diff == 0:
            continue

        sign = "+" if diff > 0 else "-"
        abs_diff = abs(diff)

        if diff > tol:
            tag = "OVERSUPPLY"
        elif diff < -tol:
            tag = "UNDERSUPPLY"
        else:
            tag = "WITHIN 0.50"

        mismatches.append(
            f"{product}: PO {_fmt2(po_qty)} → Received {_fmt2(actual)} ({sign}{_fmt2(abs_diff)}; {tag})"
        )

    if not mismatches:
        return "All received quantities match the PO."

    shown = mismatches[:max_lines]
    remaining = len(mismatches) - len(shown)

    rows.extend(shown)
    if remaining > 0:
        rows.append(f"+ {remaining} more variance lines")

    return "\n".join(rows)


def _receiving_queried_lines_details(receiving, max_lines=6):
    qs = (
        receiving.items
        .filter(accounting_queried=True)
        .select_related("po_item__product")
    )
    items = list(qs)
    if not items:
        return ""

    lines = []
    for ri in items[:max_lines]:
        product = getattr(ri.po_item.product, "name", str(ri.po_item.product))
        note = (ri.accounting_notes or "").strip()
        if note:
            lines.append(f"{product}: {note}")
        else:
            lines.append(f"{product}: queried")

    remaining = len(items) - min(len(items), max_lines)
    if remaining > 0:
        lines.append(f"+ {remaining} more queried lines")

    return "Queried lines:\n" + "\n".join(lines)
