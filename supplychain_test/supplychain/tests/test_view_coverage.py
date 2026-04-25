from decimal import Decimal
from io import StringIO
from unittest.mock import patch

import pandas as pd
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from model_bakery import baker

from supplychain.models import (
    Category,
    Destination,
    LowStockAlert,
    Payment,
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    Receiving,
    ReceivingItem,
    Requisition,
    RequisitionItem,
    StockTransaction,
    Supplier,
    UnitOfMeasure,
)
from supplychain.views.dashboard_views import DashboardView
from supplychain.views.inventory_views import (
    InventoryDetailView,
    InventoryFilterForm,
    InventoryListView,
    InventoryMovementFilterForm,
    InventoryMovementReportView,
    LowStockDashboardView,
    _coalesce_decimal,
    _last_movement_subquery,
    _signed_case_for_txn_queryset,
    _signed_qty_expr,
)
from supplychain.views.payments_views import PaymentDetailView, PaymentsListView
from supplychain.views.product_bulk_upload_views import ProductBulkUploadView
from supplychain.views.purchaseorder_views import (
    PurchaseOrderDetailView,
    PurchaseOrderListView,
    PurchaseOrderPendingListView,
)
from supplychain.views.receiving_views import ReceivingDetailView, ReceivingListView
from supplychain.views.requisition_views import (
    RequisitionAllListView,
    RequisitionDetailView,
    RequisitionListView,
    RequisitionPendingListView,
    _on_hand_map,
    _signed_case_for_stock,
    _validate_store_stock,
)

User = get_user_model()


class ViewCoverageBase(TestCase):
    def setUp(self):
        self.rf = RequestFactory()
        self.client = Client()
        self.user = User.objects.create_user("viewer", email="viewer@example.com", password="pw", is_superuser=True, is_staff=True)
        self.supplier = baker.make(Supplier, name="View Supplier")
        self.uom = baker.make(UnitOfMeasure, code="VC", name="View Count")
        self.product = baker.make(Product, name="View Product", uom=self.uom, unit_cost=Decimal("4.00"), low_stock_threshold=Decimal("3.00"))
        self.category = baker.make(Category, name="View Category")
        self.product.categories.add(self.category)
        self.po = baker.make(PurchaseOrder, supplier=self.supplier, created_by=self.user, status=PurchaseOrder.PENDING_COO)
        self.po_item = baker.make(PurchaseOrderItem, purchase_order=self.po, product=self.product, quantity=Decimal("2.00"), unit_cost=Decimal("4.00"))
        self.receiving = baker.make(Receiving, purchase_order=self.po, status=Receiving.PENDING)
        self.receiving_item = baker.make(ReceivingItem, receiving=self.receiving, po_item=self.po_item, actual_quantity=None)

    def request(self, method="get", path="/", data=None, files=None):
        req = getattr(self.rf, method)(path, data=data or {}, **({"FILES": files} if files else {}))
        req.user = self.user
        return req

    def capture_render(self, module_path):
        return patch(f"{module_path}.render", side_effect=lambda request, template, context: {"template": template, "context": context})


class InventoryViewsCoverageTests(ViewCoverageBase):
    def test_filter_forms_and_expression_helpers(self):
        self.assertTrue(InventoryFilterForm({"q": "view", "category": str(self.category.id), "below": "on"}).is_valid())
        form = InventoryMovementFilterForm({"start": "2026-01-02", "end": "2026-01-01"})
        self.assertFalse(form.is_valid())
        self.assertIsNotNone(_signed_qty_expr())
        self.assertIsNotNone(_coalesce_decimal(_signed_qty_expr()))
        self.assertIsNotNone(_last_movement_subquery())
        self.assertIsNotNone(_signed_case_for_txn_queryset())

    def test_inventory_list_queryset_context_detail_low_stock_and_report(self):
        StockTransaction.objects.create(product=self.product, transaction_type=StockTransaction.RECEIVE, quantity=Decimal("5.00"), source_type="X", source_id=1)
        StockTransaction.objects.create(product=self.product, transaction_type=StockTransaction.ISSUE, quantity=Decimal("2.00"), source_type="Y", source_id=2)
        LowStockAlert.objects.create(product=self.product, threshold=Decimal("3.00"))

        list_view = InventoryListView(); list_view.request = self.request("get", "/inventory/"); list_view.kwargs = {}
        qs = list_view.get_queryset()
        list_view.object_list = qs
        ctx = list_view.get_context_data(object_list=qs)
        self.assertEqual(ctx["section"], "inventory")
        self.assertEqual(ctx["active_low_stock_count"], 1)
        self.assertEqual(qs.get(pk=self.product.pk).on_hand, Decimal("3"))

        with self.capture_render("supplychain.views.inventory_views") as mocked_render:
            LowStockDashboardView().get(self.request("get"), )
            low_ctx = mocked_render.call_args.args[2]
            self.assertEqual(low_ctx["alerts"][0].current_on_hand, Decimal("3"))

        with self.capture_render("supplychain.views.inventory_views") as mocked_render:
            InventoryDetailView().get(self.request("get", f"/inventory/{self.product.pk}/?page=1"), self.product.pk)
            detail_ctx = mocked_render.call_args.args[2]
            self.assertEqual(detail_ctx["on_hand"], Decimal("3"))
            self.assertEqual(detail_ctx["active_alert"].product, self.product)

        with self.capture_render("supplychain.views.inventory_views") as mocked_render:
            InventoryMovementReportView().get(self.request("get", f"/inventory/report/?q=View&category={self.category.id}"))
            report_ctx = mocked_render.call_args.args[2]
            self.assertEqual(report_ctx["section"], "inventory")
            self.assertTrue(list(report_ctx["per_product"]))
            self.assertTrue(list(report_ctx["top_issued"]))


class PaymentAndBulkUploadViewsCoverageTests(ViewCoverageBase):
    def test_payment_list_detail_get_invalid_post_valid_post_and_processed_post(self):
        payment = baker.make(Payment, purchase_order=self.po, created_by=self.user, status=Payment.PENDING)
        receiving = self.receiving
        receiving.supplier_invoice = "invoices/test.pdf"
        receiving.save(update_fields=["supplier_invoice"])

        list_view = PaymentsListView(); list_view.request = self.request("get", "/payments/?status=PENDING"); list_view.kwargs = {}
        qs = list_view.get_queryset()
        list_view.object_list = qs
        ctx = list_view.get_context_data(object_list=qs)
        self.assertEqual(ctx["payments"][0].po_total, Decimal("8.00"))
        self.assertEqual(ctx["payments"][0].receiving_id, receiving.id)

        view = PaymentDetailView()
        with self.capture_render("supplychain.views.payments_views") as mocked_render:
            view.get(self.request("get"), payment.pk)
            self.assertIsNotNone(mocked_render.call_args.args[2]["form"])

        with self.capture_render("supplychain.views.payments_views") as mocked_render:
            resp = view.post(self.request("post", data={}), payment.pk)
            self.assertEqual(resp["context"]["payment"], payment)

        with patch("supplychain.views.payments_views.messages"):
            response = view.post(self.request("post", data={"payment_type": Payment.CHEQUE, "cheque_number": "123"}), payment.pk)
            self.assertEqual(response.status_code, 302)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.PROCESSED)
        self.assertEqual(payment.processed_by, self.user)

        with patch("supplychain.views.payments_views.messages"):
            response = view.post(self.request("post"), payment.pk)
            self.assertEqual(response.status_code, 302)

    def test_product_bulk_upload_view_get_invalid_unsupported_success_warning_and_exception(self):
        view = ProductBulkUploadView()
        with self.capture_render("supplychain.views.product_bulk_upload_views") as mocked_render:
            view.get(self.request("get"))
            self.assertEqual(mocked_render.call_args.args[2]["section"], "operations")

        with self.capture_render("supplychain.views.product_bulk_upload_views") as mocked_render, patch("supplychain.views.product_bulk_upload_views.messages"):
            view.post(self.request("post", data={}))
            self.assertEqual(mocked_render.call_args.args[2]["section"], "operations")

        bad_file = SimpleUploadedFile("bad.txt", b"x", content_type="text/plain")
        with self.capture_render("supplychain.views.product_bulk_upload_views"), patch("supplychain.views.product_bulk_upload_views.messages") as msgs:
            view.post(self.request("post", data={"file": bad_file}, files={"file": bad_file}))
            msgs.error.assert_called()

        csv_file = SimpleUploadedFile("products.csv", b"name,unit_cost,uom_code,stock_level\nA,1,EA,0\n", content_type="text/csv")
        with self.capture_render("supplychain.views.product_bulk_upload_views") as mocked_render, patch("supplychain.views.product_bulk_upload_views.import_products_df", return_value={"created": 1, "updated": 0, "inventory_adjusted": 0, "errors": []}), patch("supplychain.views.product_bulk_upload_views.messages") as msgs:
            view.post(self.request("post", data={"file": csv_file}, files={"file": csv_file}))
            msgs.success.assert_called()
            self.assertEqual(mocked_render.call_args.args[2]["result"]["created"], 1)

        xlsx_file = SimpleUploadedFile("products.xlsx", b"fake", content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with self.capture_render("supplychain.views.product_bulk_upload_views"), patch("supplychain.views.product_bulk_upload_views.pd.read_excel", side_effect=Exception("boom")), patch("supplychain.views.product_bulk_upload_views.messages") as msgs:
            view.post(self.request("post", data={"file": xlsx_file}, files={"file": xlsx_file}))
            msgs.error.assert_called()


class PurchaseReceivingDashboardViewCoverageTests(ViewCoverageBase):
    def test_dashboard_counts_with_and_without_approval_permission(self):
        Requisition.objects.create(requester=self.user, destination=Destination.objects.get_or_create(name=Destination.PURCHASE)[0], supplier=self.supplier, status=Requisition.PENDING)
        LowStockAlert.objects.create(product=self.product, threshold=Decimal("3.00"))
        view = DashboardView(); view.request = self.request("get")
        ctx = view.get_context_data()
        self.assertEqual(ctx["section"], "dashboard")
        self.assertEqual(ctx["user_reqs_count"], 1)
        self.assertEqual(ctx["pending_reqs_count"], 1)
        self.assertEqual(ctx["low_stock_count"], 1)

    def test_purchase_order_list_pending_detail_get_and_posts(self):
        req = self.request("get", f"/po/?supplier={self.supplier.pk}&status={PurchaseOrder.PENDING_COO}")
        view = PurchaseOrderListView(); view.request = req; view.kwargs = {}
        qs = view.get_queryset(); view.object_list = qs
        ctx = view.get_context_data(object_list=qs)
        self.assertEqual(ctx["section"], "purchase_orders")
        self.assertIn(self.po, list(qs))

        pending = PurchaseOrderPendingListView(); pending.request = req; pending.kwargs = {}
        pqs = pending.get_queryset(); pending.object_list = pqs
        self.assertIn(self.po, list(pqs))
        self.assertEqual(pending.get_context_data(object_list=pqs)["section"], "purchase_orders")

        detail = PurchaseOrderDetailView()
        with self.capture_render("supplychain.views.purchaseorder_views") as mocked_render:
            detail.get(self.request("get"), self.po.pk)
            self.assertTrue(mocked_render.call_args.args[2]["can_approve"])

        with self.capture_render("supplychain.views.purchaseorder_views"):
            response = detail.post(self.request("post", data={}), self.po.pk)
            self.assertIn("approval_form", response["context"])

        with patch("supplychain.views.purchaseorder_views.messages"):
            response = detail.post(self.request("post", data={"action": PurchaseOrder.APPROVED, "notes": "ok"}), self.po.pk)
            self.assertEqual(response.status_code, 302)
        self.po.refresh_from_db()
        self.assertEqual(self.po.status, PurchaseOrder.APPROVED)
        self.assertTrue(self.po.receivings.exists())

        with patch("supplychain.views.purchaseorder_views.messages"):
            response = detail.post(self.request("post", data={"action": PurchaseOrder.DENIED}), self.po.pk)
            self.assertEqual(response.status_code, 302)

    def test_receiving_list_detail_modes_helpers_and_posts(self):
        view = ReceivingListView(); view.request = self.request("get", "/receiving/?status=PENDING"); view.kwargs = {}
        qs = view.get_queryset(); view.object_list = qs
        self.assertTrue(view.has_permission())
        self.assertIn(self.receiving, list(qs))
        self.assertEqual(view.get_context_data(object_list=qs)["section"], "receiving")

        detail = ReceivingDetailView()
        self.assertEqual(detail._get_mode(self.request("get"), self.receiving), "entry")
        self.assertFalse(detail._requires_coo_approval(self.receiving))
        self.assertEqual(detail._annotate_variance_obj(self.receiving_item).variance_text, "Not recorded yet")

        self.receiving_item.actual_quantity = Decimal("2.25"); self.receiving_item.save(update_fields=["actual_quantity"])
        self.assertIn("Slightly oversupplied", detail._annotate_variance_obj(self.receiving_item).variance_text)
        self.receiving_item.actual_quantity = Decimal("4.00"); self.receiving_item.save(update_fields=["actual_quantity"])
        self.assertTrue(detail._requires_coo_approval(self.receiving))
        self.assertIn("Oversupplied", detail._annotate_variance_obj(self.receiving_item).variance_text)

        with self.capture_render("supplychain.views.receiving_views") as mocked_render:
            detail.get(self.request("get"), self.receiving.pk)
            self.assertEqual(mocked_render.call_args.args[2]["mode"], "entry")

        with self.capture_render("supplychain.views.receiving_views"):
            response = detail.post(self.request("post", data={}), self.receiving.pk)
            self.assertIn("item_formset", response["context"])

        # Accounting review: invalid action, send to COO, then COO invalid and approve.
        self.receiving.status = Receiving.UNDER_REVIEW
        self.receiving.received_at = timezone.now()
        self.receiving.received_by = self.user
        self.receiving.save()
        prefix = "items"
        base_formset = {
            f"{prefix}-TOTAL_FORMS": "1",
            f"{prefix}-INITIAL_FORMS": "1",
            f"{prefix}-MIN_NUM_FORMS": "0",
            f"{prefix}-MAX_NUM_FORMS": "1000",
            f"{prefix}-0-id": str(self.receiving_item.id),
            f"{prefix}-0-accounting_notes": "looks high",
        }
        with self.capture_render("supplychain.views.receiving_views"), patch("supplychain.views.receiving_views.messages"):
            response = detail.post(self.request("post", data={**base_formset, "accounting_action": ""}), self.receiving.pk)
            self.assertIn("accounting_formset", response["context"])

        with patch("supplychain.views.receiving_views.messages"):
            response = detail.post(self.request("post", data={**base_formset, "accounting_action": "SEND_COO", "review_notes": "needs COO"}), self.receiving.pk)
            self.assertEqual(response.status_code, 302)
        self.receiving.refresh_from_db()
        self.assertIsNotNone(self.receiving.sent_to_coo_at)
        self.assertEqual(detail._get_mode(self.request("get"), self.receiving), "coo_approval")

        with self.capture_render("supplychain.views.receiving_views"), patch("supplychain.views.receiving_views.messages"):
            response = detail.post(self.request("post", data={"coo_action": ""}), self.receiving.pk)
            self.assertIn("receiving_items", response["context"])

        with patch("supplychain.views.receiving_views.messages"):
            response = detail.post(self.request("post", data={"coo_action": "APPROVE", "coo_notes": "fine"}), self.receiving.pk)
            self.assertEqual(response.status_code, 302)
        self.receiving.refresh_from_db()
        self.assertEqual(self.receiving.status, Receiving.REVIWED)
        self.assertTrue(Payment.objects.filter(purchase_order=self.po).exists())

        with patch("supplychain.views.receiving_views.messages"):
            response = detail.post(self.request("post"), self.receiving.pk)
            self.assertEqual(response.status_code, 302)


class AccountsViewsCoverageTests(TestCase):
    @override_settings(APP_BASE_URL="https://example.test", EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", DEFAULT_FROM_EMAIL="noreply@example.test")
    def test_invite_flow_create_resend_existing_and_done(self):
        client = Client()
        admin = User.objects.create_superuser("admin", email="admin@example.test", password="pw")
        client.force_login(admin)
        with patch("accounts.views._send_set_password_email", return_value=1) as send:
            response = client.post(reverse("accounts:invite_user"), {"email": "NEW@EXAMPLE.TEST", "groups": []})
            self.assertEqual(response.status_code, 302)
            invited = User.objects.get(email="new@example.test")
            self.assertFalse(invited.has_usable_password())
            self.assertEqual(send.call_count, 1)
            response = client.post(reverse("accounts:invite_user"), {"email": "new@example.test", "groups": []})
            self.assertEqual(response.status_code, 302)
            self.assertEqual(send.call_count, 2)
        response = client.get(reverse("accounts:invite_user"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(client.get(reverse("accounts:invite_done")).status_code, 200)

        User.objects.create_user("existing", email="existing@example.test", password="pw")
        response = client.post(reverse("accounts:invite_user"), {"email": "existing@example.test", "groups": []})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "User already exists")

    @override_settings(APP_BASE_URL="https://example.test", EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", DEFAULT_FROM_EMAIL="noreply@example.test")
    def test_send_set_password_email_and_missing_base_url(self):
        from accounts.views import _send_set_password_email
        user = User.objects.create_user("mail", email="mail@example.test")
        self.assertEqual(_send_set_password_email(self.client.request().wsgi_request, user, user.email), 1)
        with override_settings(APP_BASE_URL=""):
            with self.assertRaisesMessage(RuntimeError, "APP_BASE_URL"):
                _send_set_password_email(self.client.request().wsgi_request, user, user.email)


class RequisitionViewsAdditionalCoverageTests(ViewCoverageBase):
    def test_stock_helpers_and_validate_store_stock(self):
        self.assertIsNotNone(_signed_case_for_stock())
        self.assertEqual(_on_hand_map([]), {})
        StockTransaction.objects.create(product=self.product, transaction_type=StockTransaction.RECEIVE, quantity=Decimal("2.00"), source_type="R", source_id=1)
        self.assertEqual(_on_hand_map([self.product.id, 999999])[self.product.id], Decimal("2"))
        self.assertEqual(_on_hand_map([self.product.id, 999999])[999999], Decimal("0.00"))

        class FakeForm:
            def __init__(self, product, qty):
                self.cleaned_data = {"product": product, "quantity": qty}
                self.errors = {}
            def add_error(self, field, message):
                self.errors[field] = message

        class FakeFormSet:
            forms = []

        form1 = FakeForm(self.product, Decimal("1.50"))
        form2 = FakeForm(self.product, Decimal("1.00"))
        fs = FakeFormSet(); fs.forms = [form1, form2]
        _validate_store_stock(fs)
        self.assertIn("quantity", form1.errors)
        empty_product = baker.make(Product, name="Empty Store Product", uom=self.uom)
        form3 = FakeForm(empty_product, Decimal("1.00"))
        fs.forms = [form3]
        _validate_store_stock(fs)
        self.assertIn("product", form3.errors)

    def _make_req(self, *, requester=None, destination=None, supplier=None, status=Requisition.PENDING):
        return Requisition.objects.create(
            requester=requester or self.user,
            destination=destination or Destination.objects.get_or_create(name=Destination.PURCHASE)[0],
            supplier=supplier or self.supplier,
            status=status,
            notes="note",
        )

    def test_requisition_list_pending_all_querysets_and_contexts(self):
        store = Destination.objects.get_or_create(name=Destination.STORE)[0]
        other = User.objects.create_user("other")
        mine = self._make_req(status=Requisition.PENDING)
        theirs = self._make_req(requester=other, destination=store, supplier=None, status=Requisition.APPROVED)

        list_view = RequisitionListView(); list_view.request = self.request("get"); list_view.kwargs = {}
        qs = list_view.get_queryset(); list_view.object_list = qs
        self.assertEqual(list(qs), [mine])
        self.assertEqual(list_view.get_context_data(object_list=qs)["section"], "requisitions")

        pending = RequisitionPendingListView(); pending.request = self.request("get", f"/req/pending/?requester={self.user.pk}&destination={mine.destination.pk}&urgent=no"); pending.kwargs = {}
        pqs = pending.get_queryset(); pending.object_list = pqs
        pctx = pending.get_context_data(object_list=pqs)
        self.assertEqual(pctx["active_status"], Requisition.PENDING)
        self.assertIn(mine, list(pqs))
        self.assertNotIn(theirs, list(pqs))

        all_view = RequisitionAllListView(); all_view.request = self.request("get", f"/req/all/?status={Requisition.APPROVED}&destination={store.pk}&urgent=no"); all_view.kwargs = {}
        aqs = all_view.get_queryset(); all_view.object_list = aqs
        actx = all_view.get_context_data(object_list=aqs)
        self.assertEqual(actx["active_status"], Requisition.APPROVED)
        self.assertIn(theirs, list(aqs))

    def test_requisition_detail_get_permission_paths_and_approval_paths(self):
        purchase = Destination.objects.get_or_create(name=Destination.PURCHASE)[0]
        store = Destination.objects.get_or_create(name=Destination.STORE)[0]
        req = self._make_req(destination=purchase, status=Requisition.PENDING)
        RequisitionItem.objects.create(requisition=req, product=self.product, quantity=Decimal("1.00"))
        view = RequisitionDetailView()

        with self.capture_render("supplychain.views.requisition_views") as mocked_render:
            view.get(self.request("get"), req.pk)
            ctx = mocked_render.call_args.args[2]
            self.assertTrue(ctx["can_approve"])
            self.assertIsNotNone(ctx["approval_form"])

        outsider = User.objects.create_user("outsider")
        outsider_req = self.request("get"); outsider_req.user = outsider
        with patch("supplychain.views.requisition_views.messages"):
            response = view.get(outsider_req, req.pk)
            self.assertEqual(response.status_code, 302)

        with self.capture_render("supplychain.views.requisition_views") as mocked_render:
            view.post(self.request("post", data={}), req.pk)
            self.assertIn("approval_form", mocked_render.call_args.args[2])

        with patch("supplychain.views.requisition_views.transaction.on_commit", lambda func: None), patch("supplychain.views.requisition_views.messages"):
            response = view.post(self.request("post", data={"action": Requisition.APPROVED, "notes": "ok"}), req.pk)
            self.assertEqual(response.status_code, 302)
        req.refresh_from_db()
        self.assertEqual(req.status, Requisition.APPROVED)
        self.assertTrue(PurchaseOrder.objects.filter(requisition=req).exists())

        with patch("supplychain.views.requisition_views.messages"):
            response = view.post(self.request("post", data={"action": Requisition.DENIED}), req.pk)
            self.assertEqual(response.status_code, 302)

        store_req = self._make_req(destination=store, supplier=None, status=Requisition.PENDING)
        RequisitionItem.objects.create(requisition=store_req, product=self.product, quantity=Decimal("1.00"))
        StockTransaction.objects.create(product=self.product, transaction_type=StockTransaction.RECEIVE, quantity=Decimal("5.00"), source_type="seed", source_id=7)
        with patch("supplychain.views.requisition_views.transaction.on_commit", lambda func: None), patch("supplychain.views.requisition_views.messages"):
            response = view.post(self.request("post", data={"action": Requisition.APPROVED}), store_req.pk)
            self.assertEqual(response.status_code, 302)
        self.assertTrue(StockTransaction.objects.filter(source_type=StockTransaction.SRC_REQUISITION, source_id=store_req.pk).exists())

        no_perm = self.request("post"); no_perm.user = outsider
        with patch("supplychain.views.requisition_views.messages"):
            response = view.post(no_perm, store_req.pk)
            self.assertEqual(response.status_code, 302)


class PdfExportViewCoverageTests(ViewCoverageBase):
    def test_visible_table_pdf_export_returns_download(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("supplychain:table-pdf-export"), {
            "title": "Filtered Inventory",
            "subtitle": "Search: View Product",
            "headers": '["Product", "Qty"]',
            "rows": '[["View Product", "3.00"]]',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_inventory_record_pdf_export_returns_download(self):
        StockTransaction.objects.create(
            product=self.product,
            transaction_type=StockTransaction.RECEIVE,
            quantity=Decimal("5.00"),
            source_type=StockTransaction.SRC_BULK_UPLOAD,
            source_id=1,
            created_by=self.user,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("supplychain:record-pdf-export", args=["inventory", self.product.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("inventory-", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))

class RecordCsvExportViewCoverageTests(ViewCoverageBase):
    def test_purchase_order_record_csv_export_includes_line_data(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("supplychain:record-csv-export", args=["purchase-order", self.po.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("purchase-order-", response["Content-Disposition"])
        body = response.content.decode("utf-8")
        self.assertIn("Purchase Order", body)
        self.assertIn("View Supplier", body)
        self.assertIn("View Product", body)
        self.assertIn("Line Total", body)

    def test_purchase_order_record_pdf_contains_line_data_text(self):
        from pypdf import PdfReader
        from io import BytesIO

        self.client.force_login(self.user)
        response = self.client.get(reverse("supplychain:record-pdf-export", args=["purchase-order", self.po.pk]))

        self.assertEqual(response.status_code, 200)
        text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(response.content)).pages)
        self.assertIn("Purchase Order", text)
        self.assertIn("View Supplier", text)
        self.assertIn("View Product", text)
        self.assertIn("Line Total", text)
