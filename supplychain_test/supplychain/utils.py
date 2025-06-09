# supplychain/utils.py

from .models import PurchaseOrder, PurchaseOrderItem

def generate_po_for_requisition(requisition, created_by):
    """
    Helper to create a PurchaseOrder from an approved Requisition.
    """
    # If there’s already a PO, do nothing
    if hasattr(requisition, 'purchase_order'):
        return requisition.purchase_order

    # Determine supplier (choose first vendor on first item)
    first_item = requisition.items.first()
    vendor = first_item.product.vendors.first() if first_item else None
    if vendor is None:
        raise ValueError("Cannot create PO: no supplier found for requisition items")

    po = PurchaseOrder.objects.create(
        requisition=requisition,
        supplier=vendor,
        created_by=created_by,
        status=PurchaseOrder.PENDING_COO,  # “Pending Mum”
    )
    for item in requisition.items.all():
        PurchaseOrderItem.objects.create(
            purchase_order=po,
            product=item.product,
            quantity=item.quantity,
            unit_cost=item.product.unit_cost,
        )
    return po
