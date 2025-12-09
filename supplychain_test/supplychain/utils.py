

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

def generate_receiving_for_purchase_order(purchase_order):
    """
    Auto-create a Receiving (and ReceivingItems) for a given approved PO.

    - If a Receiving already exists for this PO, return it (or list if multiple).
    - New Receiving starts in PENDING status (awaiting physical receipt).
    - One ReceivingItem is created per PurchaseOrderItem with initial
      actual_quantity = PO quantity (you can change this to 0 if preferred).
    """
    existing = purchase_order.receivings.all()
    if existing.exists():
        return existing[0] if existing.count() == 1 else list(existing)

    with transaction.atomic():
        receiving = Receiving.objects.create(
            purchase_order=purchase_order,
            status=Receiving.PENDING,
            # received_by, received_at, supplier_invoice default to None
        )

        for po_item in purchase_order.items.all():
            ReceivingItem.objects.create(
                receiving=receiving,
                po_item=po_item,
                actual_quantity=Decimal("0.00"),  # or Decimal('0') if you prefer
                flagged_for={},
            )

    return receiving

def build_workitem_timeline(requisition):
    """
    Unified workflow timeline rooted at a Requisition.

    Shows:
    - Requisition creation
    - Requisition approvals / conversations
    - All purchase orders linked to this requisition
      (created automatically or manually)
    - PO approvals
    - Payment (if any)
    - IssuanceRequest (if any)
    """
    events = []

    # 1. Requisition created
    events.append({
        "timestamp": requisition.created_at,
        "who": requisition.requester,
        "label": f"Requisition #{requisition.id} created",
        "details": "",
    })

    # 2. All requisition approvals & conversations
    for a in requisition.approvals.select_related("approver"):
        events.append({
            "timestamp": a.timestamp,
            "who": a.approver,
            "label": f"Requisition {a.action}",
            "details": a.notes,
        })

    # 3. All purchase orders associated to this requisition
    #    (covers auto-generated POs and manual POs that link a requisition)
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

        # PO approvals / queries / denies
        for a in po.approvals.all():
            events.append({
                "timestamp": a.timestamp,
                "who": a.approver,
                "label": f"PO {a.action}",
                "details": a.notes,
            })

        # Payment, if you have a one-to-one payment model
        payment = getattr(po, "payment", None)
        if payment:
            events.append({
                "timestamp": payment.processed_at,
                "who": getattr(payment, "processed_by", None),
                "label": f"Payment processed ({payment.payment_type})",
                "details": payment.payment_notes,
            })

        # Later if you add receiving records tied to PO, add them here too.

    # 4. Issuance (currently linked from requisition)
    issuance = getattr(requisition, "issuance_request", None)
    if issuance:
        events.append({
            "timestamp": issuance.created_at,
            "who": issuance.requester,
            "label": f"IssuanceRequest #{issuance.id} created",
            "details": "",
        })
        # If you later add issuance approvals / completions, append them here.

    # 5. Sort chronologically
    events.sort(key=lambda e: e["timestamp"])
    return events


    
def build_workitem_timeline_for_po(po):
    """
    Unified workflow timeline starting from a PurchaseOrder.

    - If the PO is linked to a requisition, reuse the requisition-rooted
      timeline so you see the full life cycle from requisition through PO.
    - If there is no requisition (manual PO), build a PO-only timeline.
    """
    if po.requisition_id:
        # Re-use the one canonical workflow builder.
        return build_workitem_timeline(po.requisition)

    # Manual PO with no requisition – PO is the root.
    events = [{
        "timestamp": po.created_at,
        "who": po.created_by,
        "label": f"PO #{po.id} created",
        "details": f"Supplier: {po.supplier}",
    }]

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
            "who": getattr(payment, "processed_by", None),
            "label": f"Payment processed ({payment.payment_type})",
            "details": payment.payment_notes,
        })

    # If you later model receiving/issuance directly from PO, add them here.

    events.sort(key=lambda e: e["timestamp"])
    return events



    
