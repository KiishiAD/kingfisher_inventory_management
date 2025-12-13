

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
    Create PurchaseOrder(s) for a requisition.

    NEW RULE (based on your model change):
      - Supplier is on the Requisition header (requisition.supplier)
      - RequisitionItem no longer has supplier

    Behaviour:
      - If a PO already exists for this requisition, return it (or list if multiple).
      - Create one PO (single supplier). If no supplier on requisition, fall back to product vendor.
    """
    existing = PurchaseOrder.objects.filter(requisition=requisition)
    if existing.exists():
        return existing[0] if existing.count() == 1 else list(existing)

    # Pull items efficiently (NO supplier select_related anymore)
    items = list(requisition.items.select_related("product").all())
    if not items:
        raise ValueError("Cannot create PO: requisition has no items.")

    # Primary supplier now comes from requisition header
    header_supplier = getattr(requisition, "supplier", None)

    # If requisition has no supplier, try to infer one (only if products have vendors)
    supplier = header_supplier
    if supplier is None:
        # Try to find first available vendor among products
        for item in items:
            vendors_qs = getattr(item.product, "vendors", None)
            if vendors_qs is not None:
                supplier = vendors_qs.first()
                if supplier:
                    break

    if supplier is None:
        raise ValueError(
            "Cannot create PO: requisition has no supplier and no product vendors found."
        )

    created_pos = []
    with transaction.atomic():
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
                unit_cost=getattr(item.product, "unit_cost", 0),
            )

        created_pos.append(po)

    return created_pos[0]


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
    """
    Auto-create a Receiving (and ReceivingItems) for a given approved PO.

    - If a Receiving already exists for this PO, return it (or list if multiple).
    - New Receiving starts in PENDING status.
    - One ReceivingItem per PurchaseOrderItem with actual_quantity default 0.
    """
    existing = purchase_order.receivings.all()
    if existing.exists():
        return existing[0] if existing.count() == 1 else list(existing)

    with transaction.atomic():
        receiving = Receiving.objects.create(
            purchase_order=purchase_order,
            status=Receiving.PENDING,
        )

        for po_item in purchase_order.items.select_related("product").all():
            ReceivingItem.objects.create(
                receiving=receiving,
                po_item=po_item,
                actual_quantity=Decimal("0.00"),
                flagged_for={},
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


    
