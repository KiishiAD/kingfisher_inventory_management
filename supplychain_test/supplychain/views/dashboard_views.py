from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import TemplateView, CreateView, ListView, DetailView, FormView
from django.urls import reverse_lazy
from django.contrib import messages
from django.views import View
from django.db import transaction
from accounts.models import OrganizationMembership
from ..utils import *
from ..models import Requisition, LowStockAlert
from ..forms import *


class DashboardView(LoginRequiredMixin, TemplateView):
    """User dashboard with key counts."""
    template_name = "supplychain/dashboard.html"

    def _active_organization(self):
        memberships = self.request.user.organization_memberships.select_related("organization")
        org_id = self.request.session.get("active_organization_id")
        if org_id:
            m = memberships.filter(organization_id=org_id).first()
            if m:
                return m.organization
        m = memberships.order_by("created_at").first()
        if m:
            self.request.session["active_organization_id"] = m.organization_id
            return m.organization
        return None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["section"] = "dashboard"
        organization = self._active_organization()
        context["organization"] = organization

        if organization:
            org_user_ids = OrganizationMembership.objects.filter(
                organization=organization
            ).values_list("user_id", flat=True)
            org_reqs = Requisition.objects.filter(requester_id__in=org_user_ids)
        else:
            org_reqs = Requisition.objects.none()

        context["user_reqs_count"] = org_reqs.filter(requester=self.request.user).count()
        if self.request.user.has_perm("supplychain.approve_requisition"):
            context["pending_reqs_count"] = org_reqs.filter(status=Requisition.PENDING).count()
        else:
            context["pending_reqs_count"] = 0
        context["low_stock_count"] = LowStockAlert.objects.filter(acknowledged=False).count()
        return context
