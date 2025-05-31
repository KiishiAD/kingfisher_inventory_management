from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.urls import reverse_lazy

from .models import *

class DashboardView(LoginRequiredMixin, TemplateView):
    """
    Simple dashboard that shows:
      - how many requisitions this user has created
      - how many pending requisitions exist (if the user has approver permission)
      - how many low-stock alerts are active
    """
    template_name = "supplychain/dashboard.html"
    # If not logged in, redirect to /accounts/login/ by default.
    # You can also set login_url explicitly:
    # login_url = reverse_lazy('login')

    def get_context_data(self, **kwargs):
        # First get the default context
        context = super().get_context_data(**kwargs)

        # Count how many Requisitions this user has submitted
        user_reqs = Requisition.objects.filter(requester=self.request.user)
        context["user_reqs_count"] = user_reqs.count()

        # If the user has permission to approve requisitions, count all pending ones
        if self.request.user.has_perm("requisitions.approve_requisition"):
            context["pending_reqs_count"] = Requisition.objects.filter(
                status=Requisition.PENDING
            ).count()
        else:
            context["pending_reqs_count"] = 0

        # Count unacknowledged low-stock alerts
        context["low_stock_count"] = LowStockAlert.objects.filter(
            acknowledged=False
        ).count()

        return context

