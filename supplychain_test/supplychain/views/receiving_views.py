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


class ReceivingListView(LoginRequiredMixin, TemplateView):
    """Placeholder view for goods received notes."""
    template_name = 'supplychain/receiving/list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['section'] = 'receiving'
        return context


class ReceivingRecordView(LoginRequiredMixin, TemplateView):
    """Placeholder view for recording goods received."""
    template_name = 'supplychain/receiving/record.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['section'] = 'receiving'
        return context
