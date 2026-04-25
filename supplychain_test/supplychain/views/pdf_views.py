"""PDF download views for visible lists and individual records."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.views import View

from ..models import Payment, Product, PurchaseOrder, Receiving, Requisition, StockTransaction
from ..pdf_exports import decode_table_payload, render_key_value_pdf, render_table_pdf
from ..utils import build_workitem_timeline, build_workitem_timeline_for_po


class VisibleTablePdfExportView(LoginRequiredMixin, View):
    """Download the rows currently visible on a list/search/filter page."""

    def post(self, request):
        try:
            payload = decode_table_payload(request.POST)
        except ValueError:
            return HttpResponseBadRequest("Invalid PDF export payload.")

        return render_table_pdf(
            title=payload["title"],
            subtitle=payload["subtitle"],
            headers=payload["headers"],
            rows=payload["rows"],
        )


class RecordPdfExportView(LoginRequiredMixin, View):
    """Download a PDF summary for an individual business record."""

    def get(self, request, kind: str, pk: int):
        handlers = {
            "requisition": self._requisition,
            "purchase-order": self._purchase_order,
            "receiving": self._receiving,
            "payment": self._payment,
            "inventory": self._inventory,
        }
        handler = handlers.get(kind)
        if handler is None:
            return HttpResponseBadRequest("Unknown PDF export type.")
        return handler(request, pk)

    def _requisition(self, request, pk):
        requisition = get_object_or_404(
            Requisition.objects.select_related("requester", "destination", "supplier", "Supplier_destination_sub_category"),
            pk=pk,
        )
        if not (request.user == requisition.requester or request.user.has_perm("supplychain.approve_requisition")):
            raise PermissionDenied

        items = requisition.items.select_related("product", "product__uom").all()
        approvals = requisition.approvals.select_related("approver").order_by("timestamp")
        timeline = build_workitem_timeline(requisition)
        linked_pos = PurchaseOrder.objects.filter(requisition=requisition).select_related("supplier", "created_by")

        return render_key_value_pdf(
            title=f"Requisition #{requisition.id}",
            filename=f"requisition-{requisition.id}.pdf",
            sections=[
                ("Summary", [
                    ("Requester", requisition.requester),
                    ("Status", requisition.get_status_display()),
                    ("Destination", requisition.destination),
                    ("Supplier", requisition.supplier),
                    ("Supplier Sub-Category", requisition.Supplier_destination_sub_category),
                    ("Urgent", "Yes" if requisition.urgent else "No"),
                    ("Created", requisition.created_at),
                    ("Updated", requisition.updated_at),
                    ("Evidence", getattr(requisition.evidence, "name", "")),
                    ("Notes", requisition.notes),
                ]),
            ],
            tables=[
                (
                    "Requested Items",
                    ["Product", "SKU", "Quantity", "UOM", "Unit Cost", "Line Estimate"],
                    [[
                        i.product,
                        getattr(i.product, "sku", ""),
                        i.quantity,
                        getattr(i.product, "uom", ""),
                        getattr(i.product, "unit_cost", ""),
                        (i.quantity or Decimal("0")) * (getattr(i.product, "unit_cost", Decimal("0")) or Decimal("0")),
                    ] for i in items],
                ),
                (
                    "Linked Purchase Orders",
                    ["PO", "Supplier", "Created By", "Status", "Created"],
                    [[f"#{po.id}", po.supplier, po.created_by, po.get_status_display(), po.created_at] for po in linked_pos],
                ),
                ("Approvals", ["When", "Approver", "Action", "Notes"], [[a.timestamp, a.approver, a.get_action_display(), a.notes] for a in approvals]),
                ("Timeline", ["When", "Event", "Details"], [[t.get("timestamp", ""), t.get("label", t), t.get("details", "")] for t in timeline]),
            ],
        )

    def _purchase_order(self, request, pk):
        if not request.user.has_perm("supplychain.create_purchaseorder"):
            raise PermissionDenied
        po = get_object_or_404(
            PurchaseOrder.objects.select_related("supplier", "requisition", "created_by"),
            pk=pk,
        )
        items = list(po.items.select_related("product").all())
        approvals = po.approvals.select_related("approver").order_by("timestamp")
        total = sum((item.line_total for item in items), Decimal("0"))
        timeline = build_workitem_timeline_for_po(po)

        return render_key_value_pdf(
            title=f"Purchase Order #{po.id}",
            filename=f"purchase-order-{po.id}.pdf",
            sections=[
                ("Summary", [
                    ("Supplier", po.supplier),
                    ("Requisition", f"#{po.requisition_id}" if po.requisition_id else "Manual PO"),
                    ("Created By", po.created_by),
                    ("Status", po.get_status_display()),
                    ("Created", po.created_at),
                    ("Total", total),
                ]),
            ],
            tables=[
                ("Items", ["Product", "Quantity", "Unit Cost", "Line Total"], [[i.product, i.quantity, i.unit_cost, i.line_total] for i in items]),
                ("Approvals", ["When", "Approver", "Action", "Notes"], [[a.timestamp, a.approver, a.get_action_display(), a.notes] for a in approvals]),
                ("Timeline", ["When", "Event"], [[t.get("timestamp", ""), t.get("label", t)] for t in timeline]),
            ],
        )

    def _receiving(self, request, pk):
        if not self._can_receive(request.user):
            raise PermissionDenied
        receiving = get_object_or_404(
            Receiving.objects.select_related(
                "purchase_order", "purchase_order__supplier", "received_by", "reviewed_by", "sent_to_coo_by", "coo_decision_by"
            ).prefetch_related("items__po_item__product"),
            pk=pk,
        )
        items = receiving.items.select_related("po_item__product").all()
        po = receiving.purchase_order
        timeline = build_workitem_timeline_for_po(po)

        return render_key_value_pdf(
            title=f"Receiving #{receiving.id}",
            filename=f"receiving-{receiving.id}.pdf",
            sections=[
                ("Summary", [
                    ("Purchase Order", f"PO #{po.id}"),
                    ("Supplier", po.supplier),
                    ("Status", receiving.get_status_display()),
                    ("Received By", receiving.received_by),
                    ("Received At", receiving.received_at),
                    ("Reviewed By", receiving.reviewed_by),
                    ("Reviewed At", receiving.reviewed_at),
                    ("Review Notes", receiving.review_notes),
                    ("COO Decision By", receiving.coo_decision_by),
                    ("COO Decision At", receiving.coo_decision_at),
                    ("COO Notes", receiving.coo_decision_notes),
                ]),
            ],
            tables=[
                ("Items", ["Product", "PO Qty", "Actual Qty", "Accounting Notes"], [[i.po_item.product, i.po_item.quantity, i.actual_quantity, i.accounting_notes] for i in items]),
                ("Timeline", ["When", "Event"], [[t.get("timestamp", ""), t.get("label", t)] for t in timeline]),
            ],
        )

    def _payment(self, request, pk):
        if not request.user.has_perm("supplychain.process_payment"):
            raise PermissionDenied
        payment = get_object_or_404(
            Payment.objects.select_related("purchase_order", "purchase_order__supplier", "processed_by", "created_by"),
            pk=pk,
        )
        po = payment.purchase_order
        items = list(po.items.select_related("product").all())
        total = sum((i.line_total for i in items), Decimal("0"))
        timeline = build_workitem_timeline_for_po(po)

        return render_key_value_pdf(
            title=f"Payment #{payment.id}",
            filename=f"payment-{payment.id}.pdf",
            sections=[
                ("Summary", [
                    ("Purchase Order", f"PO #{po.id}"),
                    ("Supplier", po.supplier),
                    ("Status", payment.get_status_display()),
                    ("Method", payment.get_payment_type_display() if payment.payment_type else ""),
                    ("Created By", payment.created_by),
                    ("Processed By", payment.processed_by),
                    ("Processed At", payment.processed_at),
                    ("Approved By COO", "Yes" if payment.approved_by_coo else "No"),
                    ("Bank", payment.bank_name),
                    ("Transfer Ref", payment.transfer_reference),
                    ("Cheque No.", payment.cheque_number),
                    ("Card Last 4", payment.card_last4),
                    ("Notes", payment.payment_notes),
                    ("PO Total", total),
                ]),
            ],
            tables=[
                ("PO Items", ["Product", "Quantity", "Unit Cost", "Line Total"], [[i.product, i.quantity, i.unit_cost, i.line_total] for i in items]),
                ("Timeline", ["When", "Event"], [[t.get("timestamp", ""), t.get("label", t)] for t in timeline]),
            ],
        )

    def _inventory(self, request, pk):
        if not request.user.has_perm("supplychain.view_inventory"):
            raise PermissionDenied
        product = get_object_or_404(Product.objects.select_related("uom").prefetch_related("categories"), pk=pk)
        txns = product.stock_transactions.select_related("created_by").order_by("-created_at")

        on_hand = Decimal("0")
        for txn in txns:
            if txn.transaction_type in {StockTransaction.RECEIVE, StockTransaction.ADJUST_IN}:
                on_hand += txn.quantity
            else:
                on_hand -= txn.quantity

        return render_key_value_pdf(
            title=f"Inventory: {product.name}",
            filename=f"inventory-{product.id}.pdf",
            sections=[
                ("Product", [
                    ("SKU", product.sku),
                    ("Name", product.name),
                    ("Description", product.description),
                    ("Unit Cost", product.unit_cost),
                    ("UOM", product.uom),
                    ("Categories", ", ".join(c.name for c in product.categories.all())),
                    ("Low Stock Threshold", product.low_stock_threshold),
                    ("On Hand", on_hand),
                ]),
            ],
            tables=[
                ("Stock Ledger", ["When", "Type", "Quantity", "Source", "By", "Note"], [[t.created_at, t.get_transaction_type_display(), t.quantity, f"{t.source_type} #{t.source_id}", t.created_by, t.note] for t in txns]),
            ],
        )

    @staticmethod
    def _can_receive(user):
        return (
            user.has_perm("supplychain.record_receiving")
            or user.has_perm("supplychain.review_receiving")
            or user.has_perm("supplychain.approve_receiving")
        )
