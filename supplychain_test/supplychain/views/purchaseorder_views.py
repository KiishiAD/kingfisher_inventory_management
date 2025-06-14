from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import TemplateView, CreateView, ListView, DetailView, FormView
from django.urls import reverse_lazy
from django.contrib import messages
from django.views import View
from django.db import transaction
from ..utils import *
from ..models import *
from ..forms import *


class PurchaseOrderListView(LoginRequiredMixin, TemplateView):
    """Placeholder view for purchase orders list."""
    template_name = 'supplychain/purchase_orders/list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['section'] = 'purchase_orders'
        return context


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
