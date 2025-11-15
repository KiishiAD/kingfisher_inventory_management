

from .models import (
    PurchaseOrder,
    PurchaseOrderItem,
    IssuanceRequest,
    IssuanceItem,
)
from django.db import transaction


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
    Create one PurchaseOrder per supplier found on the requisition items.
    Prefers item.supplier; falls back to product.vendors.first().
    Returns a single PO if only one created, otherwise a list of POs.
    """
    # avoid creating duplicate POs
    existing = PurchaseOrder.objects.filter(requisition=requisition)
    if existing.exists():
        return existing[0] if existing.count() == 1 else list(existing)

    # Group items by supplier
    items_by_supplier = {}
    for item in requisition.items.select_related('product', 'supplier').all():
        supplier = getattr(item, 'supplier', None)
        if not supplier:
            vendors_qs = getattr(item.product, 'vendors', None)
            supplier = vendors_qs.first() if vendors_qs is not None else None

        if supplier is None:
            raise ValueError(f"Cannot create PO: product {item.product!r} has no supplier/vendor")

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
                    unit_cost=getattr(item.product, 'unit_cost', 0),
                )
            created_pos.append(po)

    return created_pos[0] if len(created_pos) == 1 else created_pos

def generate_issuance_for_requisition(requisition, created_by):
    """Create an IssuanceRequest from an approved store requisition."""
    if hasattr(requisition, 'issuance_request'):
        return requisition.issuance_request

    iss = IssuanceRequest.objects.create(
        requester=created_by,
        status=IssuanceRequest.PENDING,
    )
    for item in requisition.items.all():
        IssuanceItem.objects.create(
            issuance_request=iss,
            product=item.product,
            quantity=item.quantity,
        )
    return iss

def build_workitem_timeline(requisition):
    events = []

    # Requisition created (no details; the initial note is logged as an approval now)
    events.append({
        "timestamp": requisition.created_at,
        "who": requisition.requester,
        "label": f"Requisition #{requisition.id} created",
        "details": "",
    })

    # All approvals & conversations (includes requester + approvers)
    for a in requisition.approvals.select_related("approver"):
        events.append({
            "timestamp": a.timestamp,
            "who": a.approver,
            "label": f"Requisition {a.action}",
            "details": a.notes,
        })

    # Purchase order (OneToOne from Requisition)
    po = getattr(requisition, "purchase_order", None)
    if po:
        events.append({
            "timestamp": po.created_at,
            "who": po.created_by,
            "label": f"PO #{po.id} created",
            "details": "",
        })

        for a in po.approvals.select_related("approver"):
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
                "who": None,  # or payment.processed_by if you add it later
                "label": f"Payment processed ({payment.payment_type})",
                "details": payment.payment_notes,
            })

    # Issuance (OneToOne from Requisition)
    issuance = getattr(requisition, "issuance_request", None)
    if issuance:
        events.append({
            "timestamp": issuance.created_at,
            "who": issuance.requester,
            "label": f"IssuanceRequest #{issuance.id} created",
            "details": "",
        })

    # Sort chronologically
    events.sort(key=lambda e: e["timestamp"])
    return events



    
