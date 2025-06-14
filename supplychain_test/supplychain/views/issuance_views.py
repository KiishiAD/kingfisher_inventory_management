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


class IssuanceListView(LoginRequiredMixin, TemplateView):
    """Placeholder view for user's issuance requests."""
    template_name = 'supplychain/issuance/list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['section'] = 'issuance'
        return context


class IssuanceCreateView(LoginRequiredMixin, TemplateView):
    """Placeholder view for submitting issuance."""
    template_name = 'supplychain/issuance/create.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['section'] = 'issuance'
        return context


class IssuancePendingListView(LoginRequiredMixin, TemplateView):
    """Placeholder view for pending issuance approvals."""
    template_name = 'supplychain/issuance/pending.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['section'] = 'issuance'
        return context
