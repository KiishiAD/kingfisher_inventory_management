from typing import List, Dict, Any
import logging

from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()
logger = logging.getLogger(__name__)


def _format_requisition_items(requisition) -> str:
    parts = []
    for item in requisition.items.select_related('product__uom').all():
        qty = item.quantity
        try:
            qty_display = int(qty) if float(qty).is_integer() else qty
        except Exception:
            qty_display = qty
        uom = getattr(item.product, 'uom', None)
        uom_name = getattr(uom, 'name', '') if uom else ''
        product_name = getattr(item.product, 'name', str(item.product))
        parts.append(f"{qty_display} {uom_name} of {product_name}" if uom_name else f"{qty_display} of {product_name}")
    return "; ".join(parts) if parts else "no items"


def _send_email_bcc(subject: str, message: str, recipients: List[str], reply_to: str | None = None) -> Dict[str, Any]:
    """Send a single email with recipients in BCC. Returns summary dict."""
    if not recipients:
        return {"recipients_count": 0, "sent": False, "error": "no recipients"}
    envelope_from = getattr(settings, "DEFAULT_FROM_EMAIL", None)
    if not envelope_from:
        logger.warning("DEFAULT_FROM_EMAIL not set; set it to noreply@kingfisher-intelligence.com in settings.")
        envelope_from = "noreply@kingfisher-intelligence.com"
    try:
        # send to envelope_from in To and everyone else in BCC
        msg = EmailMessage(subject=subject, body=message, from_email=envelope_from, to=[envelope_from], bcc=recipients)
        if reply_to:
            msg.reply_to = [reply_to]
        sent = msg.send(fail_silently=False)
        return {"recipients_count": len(recipients), "sent": bool(sent)}
    except Exception as exc:
        logger.exception("Failed to send BCC email to %d recipients", len(recipients))
        return {"recipients_count": len(recipients), "sent": False, "error": str(exc)}


def send_approval_email_to_all_users(message: str, subject: str | None = None, reply_to: str | None = None) -> Dict[str, Any]:
    subject = subject or "Requisition approved"
    qs = User.objects.exclude(email__isnull=True).exclude(email__exact="")
    recipients = [(u.email or "").strip() for u in qs if (u.email or "").strip()]
    return _send_email_bcc(subject, message, recipients, reply_to=reply_to)


def send_denial_email_to_all_users(message: str, subject: str | None = None, reply_to: str | None = None) -> Dict[str, Any]:
    subject = subject or "Requisition denied"
    qs = User.objects.exclude(email__isnull=True).exclude(email__exact="")
    recipients = [(u.email or "").strip() for u in qs if (u.email or "").strip()]
    return _send_email_bcc(subject, message, recipients, reply_to=reply_to)


def notify_requisition_approved_to_all(requisition) -> Dict[str, Any]:
    approval = requisition.approvals.select_related('approver').order_by('-timestamp').first()
    approver = approval.approver if approval else None
    ts = approval.timestamp if approval and approval.timestamp else timezone.now()
    approver_name = getattr(approver, "username", "Someone")
    approver_email = getattr(approver, "email", None)
    items_text = _format_requisition_items(requisition)
    ts_str = timezone.localtime(ts).strftime("%Y-%m-%d %H:%M")
    subject = f"Requisition #{requisition.id} approved"
    message = f"{approver_name} approved requisition #{requisition.id} for {items_text} at {ts_str}."
    return send_approval_email_to_all_users(message=message, subject=subject, reply_to=approver_email)


def notify_requisition_denied_to_all(requisition) -> Dict[str, Any]:
    approval = requisition.approvals.select_related('approver').order_by('-timestamp').first()
    approver = approval.approver if approval else None
    ts = approval.timestamp if approval and approval.timestamp else timezone.now()
    approver_name = getattr(approver, "username", "Someone")
    approver_email = getattr(approver, "email", None)
    items_text = _format_requisition_items(requisition)
    ts_str = timezone.localtime(ts).strftime("%Y-%m-%d %H:%M")
    subject = f"Requisition #{requisition.id} denied"
    message = f"{approver_name} denied requisition #{requisition.id} for {items_text} at {ts_str}."
    return send_denial_email_to_all_users(message=message, subject=subject, reply_to=approver_email)