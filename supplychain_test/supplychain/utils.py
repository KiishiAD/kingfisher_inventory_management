

from .models import (
    PurchaseOrder,
    PurchaseOrderItem,
    IssuanceRequest,
    IssuanceItem,
    Receiving,
    ReceivingItem,
)
from django.db import transaction
from decimal import Decimal


# def generate_po_for_requisition(requisition, created_by):
#     """
#     Helper to create a PurchaseOrder from an approved Requisition.
#     """
#     # If there’s already a PO, do nothing
#     if hasattr(requisition, 'purchase_order'):
#         return requisition.purchase_order

#     # Determine supplier (choose first vendor on first item)
#     first_item = requisition.items.first()
#     vendor = first_item.product.vendors.first() if first_item else None

#     po = PurchaseOrder.objects.create(
#         requisition=requisition,
#         supplier=vendor,
#         created_by=created_by,
#         status=PurchaseOrder.PENDING_COO, 
#     )
#     for item in requisition.items.all():
#         PurchaseOrderItem.objects.create(
#             purchase_order=po,
#             product=item.product,
#             quantity=item.quantity,
#             unit_cost=item.product.unit_cost,
#         )
#     return po

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
            events.append({
                "timestamp": payment.processed_at,
                "who": getattr(payment, "processed_by", None),
                "label": f"Payment processed ({payment.payment_type})",
                "details": payment.payment_notes,
            })

        # Optional: include receiving event if you want (safe, minimal)
        receiving = getattr(po, "receivings", None)
        if receiving is not None:
            rec = po.receivings.order_by("-created_at").first()
            if rec:
                events.append({
                    "timestamp": rec.created_at,
                    "who": rec.received_by,
                    "label": f"Receiving #{rec.id} created",
                    "details": f"Status: {rec.get_status_display()}",
                })

    # 4. Issuance (linked from requisition)
    issuance = getattr(requisition, "issuance_request", None)
    if issuance:
        events.append({
            "timestamp": issuance.created_at,
            "who": issuance.requester,
            "label": f"IssuanceRequest #{issuance.id} created",
            "details": "",
        })

    events.sort(key=lambda e: e["timestamp"])
    return events


def build_workitem_timeline_for_po(po):
    """
    Unified workflow timeline starting from a PurchaseOrder.
    """
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
        events.append({
            "timestamp": payment.processed_at,
            "who": getattr(payment, "processed_by", None),
            "label": f"Payment processed ({payment.payment_type})",
            "details": payment.payment_notes,
        })

    rec = po.receivings.order_by("-created_at").first()
    if rec:
        events.append({
            "timestamp": rec.created_at,
            "who": rec.received_by,
            "label": f"Receiving #{rec.id} created",
            "details": f"Status: {rec.get_status_display()}",
        })

    events.sort(key=lambda e: e["timestamp"])
    return events


    
