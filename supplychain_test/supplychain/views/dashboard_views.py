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


class DashboardView(LoginRequiredMixin, TemplateView):
    """User dashboard with key counts."""
    template_name = "supplychain/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["section"] = "dashboard"
        user_reqs = Requisition.objects.filter(requester=self.request.user)
        context["user_reqs_count"] = user_reqs.count()
        if self.request.user.has_perm("supplychain.approve_requisition"):
            context["pending_reqs_count"] = Requisition.objects.filter(
                status=Requisition.PENDING
            ).count()
        else:
            context["pending_reqs_count"] = 0
        context["low_stock_count"] = LowStockAlert.objects.filter(
            acknowledged=False
        ).count()
        return context
