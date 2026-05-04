"""Tenant utilities: permission helpers, thread-local state, and TenantManager."""

import threading

from django.contrib.auth.models import Group
from django.db import models

from supplychain.models import OrganisationMembership

_thread_local = threading.local()


def set_current_organisation(organisation):
    """Store the current organisation in thread-local storage."""
    _thread_local.organisation_id = organisation.id


def get_current_organisation_id():
    """Return the current organisation ID from thread-local storage, or None."""
    return getattr(_thread_local, "organisation_id", None)


def clear_current_organisation():
    """Clear the current organisation from thread-local storage."""
    if hasattr(_thread_local, "organisation_id"):
        del _thread_local.organisation_id


class TenantManager(models.Manager):
    """Manager that scopes querysets to the current organisation."""

    def get_queryset(self):
        qs = super().get_queryset()
        org_id = get_current_organisation_id()
        if org_id is not None:
            qs = qs.filter(organisation_id=org_id)
        return qs


def get_user_groups(user, organisation):
    """Return Group objects matching the user's roles in an organisation."""
    roles = OrganisationMembership.objects.filter(
        user=user, organisation=organisation
    ).values_list("role", flat=True)
    return list(Group.objects.filter(name__in=list(roles)))
