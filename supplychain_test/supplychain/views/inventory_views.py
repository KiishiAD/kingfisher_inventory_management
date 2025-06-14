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


class InventoryLevelsView(LoginRequiredMixin, TemplateView):
    """Placeholder view for current inventory levels."""
    template_name = 'supplychain/inventory/levels.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['section'] = 'inventory'
        return context


class InventoryAlertsView(LoginRequiredMixin, TemplateView):
    """Placeholder view for low stock alerts."""
    template_name = 'supplychain/inventory/alerts.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['section'] = 'inventory'
        return context
