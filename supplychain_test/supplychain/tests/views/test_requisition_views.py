from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission

from supplychain.models.master_data import (
    UnitOfMeasure,
    Product,
    Destination,
    Supplier,
    Supplier_destination_sub_category,
)
from supplychain.models.requisition import Requisition, RequisitionItem, RequisitionApproval
from supplychain.forms import RequisitionItemFormSet


User = get_user_model()


class RequisitionViewsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        # master data created once for the TestCase to avoid duplicate unique inserts
        cls.uom, _ = UnitOfMeasure.objects.get_or_create(code='EA', defaults={'name': 'Each'})
        cls.product, _ = Product.objects.get_or_create(name='Paper', uom=cls.uom, defaults={'unit_cost': '1.00'})
        cls.product2, _ = Product.objects.get_or_create(name='Pen', uom=cls.uom, defaults={'unit_cost': '2.00'})
        cls.supplier, _ = Supplier.objects.get_or_create(name='Acme Supplies')
        cls.destination_supplier, _ = Destination.objects.get_or_create(name=Destination.PURCHASE)
        cls.destination_store, _ = Destination.objects.get_or_create(name=Destination.STORE)
        cls.subcat, _ = Supplier_destination_sub_category.objects.get_or_create(name=Supplier_destination_sub_category.CONSUMABLES)

    def setUp(self):
        self.requester = User.objects.create_user('requester', password='pw')
        self.approver = User.objects.create_user('approver', password='pw')

        submit_perm = Permission.objects.get(codename='submit_requisition')
        approve_perm = Permission.objects.get(codename='approve_requisition')
        view_all_perm = Permission.objects.get(codename='view_all_requisitions')
        self.requester.user_permissions.add(submit_perm)
        self.approver.user_permissions.add(approve_perm)
        self.approver.user_permissions.add(view_all_perm)

        self.uom = self.__class__.uom
        self.product = self.__class__.product
        self.product2 = self.__class__.product2
        self.supplier = self.__class__.supplier
        self.destination_supplier = self.__class__.destination_supplier
        self.destination_store = self.__class__.destination_store
        self.subcat = self.__class__.subcat

        self.client = Client()

    def _upload(self, name='evidence.txt', content=b'evidence'):
        return SimpleUploadedFile(name, content, content_type='text/plain')

    def _build_item_formset_data(self, prefix, items, initial='0'):
        data = {}
        total = len(items)
        data[f'{prefix}-TOTAL_FORMS'] = str(total)
        data[f'{prefix}-INITIAL_FORMS'] = str(initial)
        data[f'{prefix}-MIN_NUM_FORMS'] = '0'
        data[f'{prefix}-MAX_NUM_FORMS'] = '1000'
        for i, item in enumerate(items):
            if 'id' in item and item['id'] is not None:
                data[f'{prefix}-{i}-id'] = str(item['id'])
            data[f'{prefix}-{i}-product'] = str(item['product'])
            data[f'{prefix}-{i}-quantity'] = str(item['quantity'])
            if item.get('DELETE'):
                data[f'{prefix}-{i}-DELETE'] = 'on'
        return data

    def test_create_requisition_and_items(self):
        self.client.force_login(self.requester)
        url = reverse('supplychain:requisition-create')
        prefix = RequisitionItemFormSet().prefix

        post = {
            'urgent': '',
            'destination': str(self.destination_supplier.id),
            'Supplier_destination_sub_category': str(self.subcat.id),
            'supplier': str(self.supplier.id),
            'notes': 'Please supply',
            'evidence': self._upload(),
        }
        post.update(self._build_item_formset_data(prefix, [{'product': self.product.id, 'quantity': '5.00'}]))

        resp = self.client.post(url, post)
        self.assertEqual(resp.status_code, 302)
        rq = Requisition.objects.filter(requester=self.requester).first()
        self.assertIsNotNone(rq)
        self.assertEqual(rq.supplier, self.supplier)
        self.assertEqual(rq.items.count(), 1)

    def test_approver_queries_and_requester_updates(self):
        rq = Requisition.objects.create(
            requester=self.requester,
            destination=self.destination_supplier,
            Supplier_destination_sub_category=self.subcat,
            supplier=self.supplier,
            evidence=self._upload(),
            notes='Initial',
            urgent=False,
        )
        item = RequisitionItem.objects.create(requisition=rq, product=self.product, quantity='2.00')

        self.client.force_login(self.approver)
        detail_url = reverse('supplychain:requisition-detail', args=[rq.id])
        resp = self.client.post(detail_url, {'action': Requisition.QUERIED, 'notes': 'Need clarification'})
        self.assertEqual(resp.status_code, 302)
        rq.refresh_from_db()
        self.assertEqual(rq.status, Requisition.QUERIED)
        self.assertTrue(rq.approvals.exists())

        self.client.force_login(self.requester)
        update_url = reverse('supplychain:requisition-update', args=[rq.id])
        get = self.client.get(update_url)
        self.assertEqual(get.status_code, 200)
        prefix = get.context['item_formset'].prefix

        post = {
            'urgent': '',
            'destination': str(self.destination_supplier.id),
            'Supplier_destination_sub_category': str(self.subcat.id),
            'supplier': str(self.supplier.id),
            'notes': 'Clarified',
        }
        post.update(self._build_item_formset_data(
            prefix,
            [{'id': item.id, 'product': self.product.id, 'quantity': '3.00'}],
            initial='1',
        ))

        resp2 = self.client.post(update_url, post)
        self.assertEqual(resp2.status_code, 302)
        rq.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(rq.status, Requisition.PENDING)
        self.assertEqual(str(item.quantity), '3.00')
        self.assertTrue(RequisitionApproval.objects.filter(requisition=rq, action=Requisition.PENDING).exists())

    def test_update_removes_line_item_when_marked_delete(self):
        rq = Requisition.objects.create(
            requester=self.requester,
            destination=self.destination_supplier,
            Supplier_destination_sub_category=self.subcat,
            supplier=self.supplier,
            evidence=self._upload(),
            notes='To delete',
            status=Requisition.QUERIED,
        )
        item1 = RequisitionItem.objects.create(requisition=rq, product=self.product, quantity='1')
        item2 = RequisitionItem.objects.create(requisition=rq, product=self.product2, quantity='2')

        self.client.force_login(self.requester)
        update_url = reverse('supplychain:requisition-update', args=[rq.id])
        get = self.client.get(update_url)
        self.assertEqual(get.status_code, 200)
        prefix = get.context['item_formset'].prefix

        post = {
            'urgent': '',
            'destination': str(self.destination_supplier.id),
            'Supplier_destination_sub_category': str(self.subcat.id),
            'supplier': str(self.supplier.id),
            'notes': 'Removing one',
        }
        post.update(self._build_item_formset_data(
            prefix,
            [
                {'id': item1.id, 'product': self.product.id, 'quantity': '1'},
                {'id': item2.id, 'product': self.product2.id, 'quantity': '2', 'DELETE': True},
            ],
            initial='2',
        ))

        resp = self.client.post(update_url, post)
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(RequisitionItem.objects.filter(id=item2.id).exists())
        self.assertTrue(RequisitionItem.objects.filter(id=item1.id).exists())
