from django import template
from django.utils.html import format_html

register = template.Library()

STATUS_CLASSES = {
    'PENDING': 'text-bg-warning',
    'APPROVED': 'text-bg-success',
    'DENIED': 'text-bg-danger',
    'QUERIED': 'text-bg-info',
}

STATUS_LABELS = {
    'PENDING': 'Pending',
    'APPROVED': 'Approved',
    'DENIED': 'Denied',
    'QUERIED': 'Queried',
}

@register.filter
def status_badge(status):
    css_class = STATUS_CLASSES.get(status, 'text-bg-secondary')
    label = STATUS_LABELS.get(status, status.title())
    return format_html('<span class="badge {}">{}</span>', css_class, label)
