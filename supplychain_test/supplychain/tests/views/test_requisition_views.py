from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission

from supplychain.models.master_data import UnitOfMeasure, Product, Destination, Supplier_destination_sub_category
from supplychain.models.requisition import Requisition, RequisitionItem, RequisitionApproval
from supplychain.forms import RequisitionItemFormSet


User = get_user_model()


class RequisitionViewsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        # master data created once for the TestCase to avoid duplicate unique inserts
        cls.uom, _ = UnitOfMeasure.objects.get_or_create(code='EA', defaults={'name': 'Each'})
        cls.product, _ = Product.objects.get_or_create(name='Paper', defaults={'unit_cost': '1.00', 'uom': cls.uom})
        cls.destination_supplier, _ = Destination.objects.get_or_create(name=Destination.SUPPLIER)
        cls.destination_store, _ = Destination.objects.get_or_create(name=Destination.STORE)
        cls.subcat, _ = Supplier_destination_sub_category.objects.get_or_create(name=Supplier_destination_sub_category.CONSUMABLES)

    def setUp(self):
        # users
        self.requester = User.objects.create_user('requester', password='pw')
        self.approver = User.objects.create_user('approver', password='pw')

        # give appropriate permissions
        submit_perm = Permission.objects.get(codename='submit_requisition')
        approve_perm = Permission.objects.get(codename='approve_requisition')
        view_all_perm = Permission.objects.get(codename='view_all_requisitions')
        self.requester.user_permissions.add(submit_perm)
        self.approver.user_permissions.add(approve_perm)
        self.approver.user_permissions.add(view_all_perm)

        # refer to shared master data
        self.uom = self.__class__.uom
        self.product = self.__class__.product
        self.destination_supplier = self.__class__.destination_supplier
        self.destination_store = self.__class__.destination_store
        self.subcat = self.__class__.subcat

        self.client = Client()

    def _build_item_formset_data(self, prefix, items):
        """Helper to build formset POST data for given items list of dicts [{'id':..., 'product':..., 'quantity':...}]"""
        data = {}
        total = len(items)
        data[f'{prefix}-TOTAL_FORMS'] = str(total)
        data[f'{prefix}-INITIAL_FORMS'] = '0'
        data[f'{prefix}-MIN_NUM_FORMS'] = '0'
        data[f'{prefix}-MAX_NUM_FORMS'] = '1000'
        for i, item in enumerate(items):
            if 'id' in item and item['id'] is not None:
                data[f'{prefix}-{i}-id'] = str(item['id'])
            data[f'{prefix}-{i}-product'] = str(item['product'])
            data[f'{prefix}-{i}-quantity'] = str(item['quantity'])
        return data

    def test_create_requisition_and_items(self):
        self.client.force_login(self.requester)
        url = reverse('supplychain:requisition-create')
        # get prefix from a formset instance
        prefix = RequisitionItemFormSet().prefix

        post = {
            'urgent': '',
            'destination': str(self.destination_supplier.id),
            'Supplier_destination_sub_category': str(self.subcat.id),
            'notes': 'Please supply',
        }
        post.update(self._build_item_formset_data(prefix, [{'product': self.product.id, 'quantity': '5.00'}]))

        resp = self.client.post(url, post)
        # successful create redirects to list
        self.assertEqual(resp.status_code, 302)
        rq = Requisition.objects.filter(requester=self.requester).first()
        self.assertIsNotNone(rq)
        self.assertEqual(rq.items.count(), 1)

    def test_approver_queries_and_requester_updates(self):
        # create initial requisition in PENDING state
        rq = Requisition.objects.create(
            requester=self.requester,
            destination=self.destination_supplier,
            Supplier_destination_sub_category=self.subcat,
            notes='Initial',
            urgent=False,
        )
        item = RequisitionItem.objects.create(requisition=rq, product=self.product, quantity='2.00')

        # approver queries the requisition
        self.client.force_login(self.approver)
        detail_url = reverse('supplychain:requisition-detail', args=[rq.id])
        resp = self.client.post(detail_url, {'action': Requisition.QUERIED, 'notes': 'Need clarification'})
        self.assertEqual(resp.status_code, 302)
        rq.refresh_from_db()
        self.assertEqual(rq.status, Requisition.QUERIED)
        self.assertTrue(rq.approvals.exists())

        # requester receives queried requisition and updates it via update view
        self.client.force_login(self.requester)
        update_url = reverse('supplychain:requisition-update', args=[rq.id])
        get = self.client.get(update_url)
        self.assertEqual(get.status_code, 200)
        prefix = get.context['item_formset'].prefix

        # modify note and quantity, resubmit
        post = {
            'urgent': '',
            'destination': str(self.destination_supplier.id),
            'Supplier_destination_sub_category': str(self.subcat.id),
            'notes': 'Clarified',
        }
        # include existing item as initial form
        post[f'{prefix}-INITIAL_FORMS'] = '1'
        post[f'{prefix}-TOTAL_FORMS'] = '1'
        post[f'{prefix}-MIN_NUM_FORMS'] = '0'
        post[f'{prefix}-MAX_NUM_FORMS'] = '1000'
        post[f'{prefix}-0-id'] = str(item.id)
        post[f'{prefix}-0-product'] = str(self.product.id)
        post[f'{prefix}-0-quantity'] = '3.00'

        resp2 = self.client.post(update_url, post)
        # update view redirects on success
        self.assertEqual(resp2.status_code, 302)
        rq.refresh_from_db()
        self.assertEqual(rq.status, Requisition.PENDING)
        # an approval log should have been created for the update
        self.assertTrue(RequisitionApproval.objects.filter(requisition=rq, action=Requisition.PENDING).exists())

    def test_update_removes_line_item_when_marked_delete(self):
        # create requisition with two items
        rq = Requisition.objects.create(
            requester=self.requester,
            destination=self.destination_supplier,
            Supplier_destination_sub_category=self.subcat,
            notes='To delete',
            status = Requisition.QUERIED
        )
        item1 = RequisitionItem.objects.create(requisition=rq, product=self.product, quantity='1')
        item2 = RequisitionItem.objects.create(requisition=rq, product=self.product, quantity='2')

        self.client.force_login(self.requester)
        update_url = reverse('supplychain:requisition-update', args=[rq.id])
        get = self.client.get(update_url)
        self.assertEqual(get.status_code, 200)
        prefix = get.context['item_formset'].prefix

        post = {
            'urgent': '',
            'destination': str(self.destination_supplier.id),
            'Supplier_destination_sub_category': str(self.subcat.id),
            'notes': 'Removing one',
        }
        # two initial forms
        post[f'{prefix}-INITIAL_FORMS'] = '2'
        post[f'{prefix}-TOTAL_FORMS'] = '2'
        post[f'{prefix}-MIN_NUM_FORMS'] = '0'
        post[f'{prefix}-MAX_NUM_FORMS'] = '1000'

        post[f'{prefix}-0-id'] = str(item1.id)
        post[f'{prefix}-0-product'] = str(self.product.id)
        post[f'{prefix}-0-quantity'] = '1'
        # mark second for delete
        post[f'{prefix}-1-id'] = str(item2.id)
        post[f'{prefix}-1-product'] = str(self.product.id)
        post[f'{prefix}-1-quantity'] = '2'
        post[f'{prefix}-1-DELETE'] = 'on'

        resp = self.client.post(update_url, post)
        self.assertEqual(resp.status_code, 302)
        # item2 should be deleted
        self.assertFalse(RequisitionItem.objects.filter(id=item2.id).exists())
        self.assertTrue(RequisitionItem.objects.filter(id=item1.id).exists())
