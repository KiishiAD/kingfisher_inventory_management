from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView, TemplateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.views import View
from django.db import transaction
from ..models import PurchaseOrder
from ..forms import RequisitionFilterForm

class PurchaseOrderListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """List purchase orders (all created purchase orders)."""
    model = PurchaseOrder
    template_name = 'supplychain/purchase_orders/list.html'
    context_object_name = 'purchase_orders'
    permission_required = 'supplychain.create_purchaseorder'
    paginate_by = 20

    def get_queryset(self):
        return PurchaseOrder.objects.all().order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['section'] = 'purchase_orders'
        return context


class PurchaseOrderDetailView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Show details for a single PurchaseOrder."""
    permission_required = 'supplychain.create_purchaseorder'

    def get(self, request, pk):
        po = get_object_or_404(PurchaseOrder, pk=pk)
        can_approve = request.user.has_perm('supplychain.approve_purchaseorder')
        context = {
            'purchase_order': po,
            'items': po.items.select_related('product').all(),
            'approvals': po.approvals.select_related('approver').order_by('timestamp'),
            'can_approve': can_approve,
            'section': 'purchase_orders',
        }
        return render(request, 'supplychain/purchase_orders/detail.html', context)

class PurchaseOrderCreateView(LoginRequiredMixin, TemplateView):
    """Placeholder view for creating a purchase order."""
    template_name = 'supplychain/purchase_orders/create.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['section'] = 'purchase_orders'
        return context


class PurchaseOrderPendingListView(LoginRequiredMixin, TemplateView):
    """Placeholder view for pending purchase order approvals."""
    template_name = 'supplychain/purchase_orders/pending.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['section'] = 'purchase_orders'
        return context
