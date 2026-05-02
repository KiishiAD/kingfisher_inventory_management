"""
Receiving-focused workflow history reader.

Prefer persisted ReceivingWorkflowHistory events; fall back to derived
audit-field events when no persisted history exists.

Each returned event dict has:
    label        — client-facing string
    details      — client-facing string (may be empty)
    who          — User FK or None
    actor_display — snapshotted name string
    when         — datetime of business occurrence
    source       — "persisted" or "derived"
"""

from django.utils import timezone

from ..models import Receiving, ReceivingWorkflowHistory


# ----------------------------------------------------------------------
# Derived fallback events
# ----------------------------------------------------------------------


def _derive_events(receiving: Receiving):
    """
    Build event dicts from Receiving audit fields.
    Used when no persisted workflow history exists.
    """
    events = []

    # Goods received
    if receiving.received_at:
        events.append({
            "label": "Receiving recorded (goods received)",
            "details": "",
            "who": receiving.received_by,
            "actor_display": _actor_name(receiving.received_by),
            "when": receiving.received_at,
            "source": "derived",
        })

    # Sent to COO
    if receiving.sent_to_coo_at:
        events.append({
            "label": "Sent to COO for approval/denial",
            "details": "",
            "who": receiving.sent_to_coo_by,
            "actor_display": _actor_name(receiving.sent_to_coo_by),
            "when": receiving.sent_to_coo_at,
            "source": "derived",
        })

    # Accounting review decision
    if receiving.reviewed_at:
        if receiving.status == Receiving.DENIED:
            label = "Accounting denied this receiving"
        elif receiving.status == Receiving.REVIWED and not receiving.coo_decision_at:
            label = "Accounting approved (cleared for payment)"
        else:
            # reviewed but no clear outcome yet
            label = "Accounting review completed"
        events.append({
            "label": label,
            "details": receiving.review_notes or "",
            "who": receiving.reviewed_by,
            "actor_display": _actor_name(receiving.reviewed_by),
            "when": receiving.reviewed_at,
            "source": "derived",
        })

    # COO decision
    if receiving.coo_decision_at:
        if receiving.status == Receiving.DENIED:
            label = "COO denied this receiving"
        else:
            label = "COO approved (cleared for payment)"
        events.append({
            "label": label,
            "details": receiving.coo_decision_notes or "",
            "who": receiving.coo_decision_by,
            "actor_display": _actor_name(receiving.coo_decision_by),
            "when": receiving.coo_decision_at,
            "source": "derived",
        })

    return events


def _actor_name(user):
    """Return stable display name for a user, or empty string."""
    if user is None:
        return ""
    name = user.get_full_name()
    if name:
        return name
    return user.get_username() or ""


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------


def get_receiving_timeline(receiving: Receiving):
    """
    Return a chronologically-ordered list of workflow event dicts for a Receiving.

    Prefers persisted ReceivingWorkflowHistory rows.
    Falls back to derived audit-field events when no persisted history exists.

    Each dict: {label, details, who, actor_display, when, source}
    Metadata keys are NOT included in returned dicts (hidden from clients).
    """
    persisted = list(
        receiving.workflow_history.all()
        .select_related("actor")
        .order_by("occurred_at", "pk")
    )

    if persisted:
        return [
            {
                "label": e.label,
                "details": e.details,
                "who": e.actor,
                "actor_display": e.actor_display,
                "when": e.occurred_at,
                "source": "persisted",
            }
            for e in persisted
        ]

    # Fallback to derived events
    return sorted(_derive_events(receiving), key=lambda e: (e["when"], ""))
