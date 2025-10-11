# ...existing code...
import os
import logging
from typing import List, Dict, Any
from ..models import Profile
import requests
from django.conf import settings
from django.utils import timezone



logger = logging.getLogger(__name__)



# prefer explicit settings, fallback to environment/default
TEXTBELT_API_KEY = getattr(settings, "TEXTBELT_API_KEY")
TEXTBELT_ENDPOINT = getattr(settings, "TEXTBELT_ENDPOINT")


def _send_textbelt(phone: str, message: str, key: str) -> Dict[str, Any]:
    """Internal: send one SMS via Textbelt and return result dict."""
    payload = {"phone": phone, "message": message, "key": key}
    try:
        resp = requests.post(TEXTBELT_ENDPOINT, data=payload, timeout=15)
        resp.raise_for_status()
        result = resp.json()
    except requests.RequestException as exc:
        logger.exception("Textbelt send failed to %s", phone)
        return {"phone": phone, "success": False, "error": str(exc), "status_code": getattr(exc.response, "status_code", None)}
    return {"phone": phone, "success": bool(result.get("success")), "response": result, "status_code": resp.status_code}

def send_approval_sms(phone: str, message: str, key: str = None) -> Dict[str, Any]:
    """Send a single approval SMS (wrapper)."""
    key = key or TEXTBELT_API_KEY
    if not key:
        raise RuntimeError("Textbelt API key not configured (TEXTBELT_API_KEY).")
    return _send_textbelt(phone, message, key)

def send_denial_sms(phone: str, message: str, key: str = None) -> Dict[str, Any]:
    """Send a single denial SMS (wrapper)."""
    key = key or TEXTBELT_API_KEY
    if not key:
        raise RuntimeError("Textbelt API key not configured (TEXTBELT_API_KEY).")
    return _send_textbelt(phone, message, key)




def send_approval_sms_to_all_profiles(message: str) -> List[Dict[str, Any]]:
    """
    Send approval message to all profiles with phone_number.
    Returns list of result dicts for each attempted send.
    """
    results: List[Dict[str, Any]] = []
    qs = Profile.objects.exclude(phone_number__isnull=True).exclude(phone_number__exact="")
    if not qs.exists():
        logger.info("No profiles with phone numbers found to send approval SMS.")
        return results

    key = TEXTBELT_API_KEY
    if not key:
        logger.warning("TEXTBELT_API_KEY not set; aborting bulk SMS send.")
        raise RuntimeError("TEXTBELT_API_KEY environment variable is required to send SMS.")

    for profile in qs:
        phone = (profile.phone_number or "").strip()
        if not phone:
            continue
        try:
            res = send_approval_sms(phone, message, key=key)
        except Exception as exc:
            logger.exception("Unexpected error sending approval SMS to %s", phone)
            res = {"phone": phone, "success": False, "error": str(exc)}
        results.append(res)
    return results



def send_denial_sms_to_all_profiles(message: str) -> List[Dict[str, Any]]:
    """
    Send denial message to all profiles with phone_number.
    Returns list of result dicts for each attempted send.
    """
    results: List[Dict[str, Any]] = []
    qs = Profile.objects.exclude(phone_number__isnull=True).exclude(phone_number__exact="")
    if not qs.exists():
        logger.info("No profiles with phone numbers found to send denial SMS.")
        return results

    key = TEXTBELT_API_KEY
    if not key:
        logger.warning("TEXTBELT_API_KEY not set; aborting bulk SMS send.")
        raise RuntimeError("TEXTBELT_API_KEY environment variable is required to send SMS.")

    for profile in qs:
        phone = (profile.phone_number or "").strip()
        if not phone:
            continue
        try:
            res = send_denial_sms(phone, message, key=key)
        except Exception as exc:
            logger.exception("Unexpected error sending denial SMS to %s", phone)
            res = {"phone": phone, "success": False, "error": str(exc)}
        results.append(res)
    return results


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

def notify_requisition_approved_to_all(requisition) -> List[Dict[str, Any]]:
    approval = requisition.approvals.select_related('approver').order_by('-timestamp').first()
    approver = approval.approver if approval else None
    ts = approval.timestamp if approval and approval.timestamp else timezone.now()
    approver_name = getattr(approver, "username", "Someone")
    items_text = _format_requisition_items(requisition)
    message = f"{approver_name} approved requisition #{requisition.id} for {items_text} at {timezone.localtime(ts).strftime('%Y-%m-%d %H:%M')}."
    return send_approval_sms_to_all_profiles(message)



def notify_requisition_denied_to_all(requisition) -> List[Dict[str, Any]]:
    approval = requisition.approvals.select_related('approver').order_by('-timestamp').first()
    approver = approval.approver if approval else None
    ts = approval.timestamp if approval and approval.timestamp else timezone.now()
    approver_name = getattr(approver, "username", "Someone")
    items_text = _format_requisition_items(requisition)
    message = f"{approver_name} denied requisition #{requisition.id} for {items_text} at {timezone.localtime(ts).strftime('%Y-%m-%d %H:%M')}."
    return send_denial_sms_to_all_profiles(message)
