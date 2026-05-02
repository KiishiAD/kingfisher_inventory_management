"""
ReceivingWorkflowService — single source of truth for Receiving workflow transitions.

All state mutations on Receiving go through this service to ensure:
- Atomic transitions with row-level locking (select_for_update)
- Audit trail via ReceivingWorkflowHistory
- Idempotent event creation
- Clear error types for invalid transitions
"""
from django.db import transaction
from django.utils import timezone

from supplychain.models import Receiving, ReceivingWorkflowHistory, Payment
from supplychain.services.inventory import record_receiving_as_stock


# --------------------------------------------------------------------------
# Domain exceptions
# --------------------------------------------------------------------------

class ReceivingNotFoundError(Exception):
    """Raised when the receiving record does not exist."""
    pass


class InvalidStatusTransitionError(Exception):
    """
    Raised when a workflow action cannot be performed in the current state.
    The .current_status and .target_status attributes describe the transition.
    """
    def __init__(self, message, current_status=None, target_status=None):
        super().__init__(message)
        self.current_status = current_status
        self.target_status = target_status


# --------------------------------------------------------------------------
# Service
# --------------------------------------------------------------------------

class ReceivingWorkflowService:
    """
    Single entry point for all Receiving workflow state transitions.

    Each public method:
    - Acquires a row-level lock via select_for_update
    - Validates the current state
    - Atomically mutates the Receiving + writes history
    - Returns the updated Receiving instance
    """

    # Valid FROM statuses for each action
    VALID_FROM_CLEAR_FOR_PAYMENT = {Receiving.UNDER_REVIEW}
    VALID_FROM_SEND_TO_COO = {Receiving.UNDER_REVIEW}
    VALID_FROM_APPROVE_COO = {Receiving.PENDING_COO}
    VALID_FROM_DENY_ACCOUNTING = {Receiving.UNDER_REVIEW, Receiving.PENDING_COO}
    VALID_FROM_DENY_COO = {Receiving.PENDING_COO}

    @classmethod
    def clear_for_payment(cls, receiving_id: int, acting_user):
        """
        Transition a receiving from UNDER_REVIEW → REVIWED (Cleared for Payment).

        This is the normal (non-COO) accounting approval path.

        Post-conditions:
        - receiving.status = REVIWED
        - receiving.accounting_approved_by = acting_user
        - receiving.accounting_approved_at = now()
        - Payment record created in PENDING state
        - Stock posted via record_receiving_as_stock
        - ReceivingWorkflowHistory entry recorded

        Raises:
            ReceivingNotFoundError: receiving_id does not exist
            InvalidStatusTransitionError: receiving not in UNDER_REVIEW
        """
        with transaction.atomic():
            try:
                receiving = (
                    Receiving.objects
                    .select_for_update()
                    .get(pk=receiving_id)
                )
            except Receiving.DoesNotExist:
                raise ReceivingNotFoundError(
                    f"Receiving {receiving_id} does not exist."
                )

            if receiving.status == Receiving.REVIWED:
                # Already cleared — idempotent no-op
                return receiving

            if receiving.status not in cls.VALID_FROM_CLEAR_FOR_PAYMENT:
                raise InvalidStatusTransitionError(
                    f"Cannot clear for payment: receiving is in status "
                    f"{receiving.status!r}, expected {Receiving.UNDER_REVIEW!r}.",
                    current_status=receiving.status,
                    target_status=Receiving.REVIWED,
                )

            receiving.status = Receiving.REVIWED
            receiving.reviewed_by = acting_user
            receiving.reviewed_at = timezone.now()
            receiving.save(update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
            ])

            # Create pending payment
            po = receiving.purchase_order
            Payment.objects.get_or_create(
                purchase_order=po,
                defaults={
                    "status": Payment.PENDING,
                    "created_by": acting_user,
                },
            )

            # Post stock
            record_receiving_as_stock(receiving.pk, acting_user.pk)

            # Write audit history
            ReceivingWorkflowHistory.objects.create_event(
                receiving=receiving,
                action_type=ReceivingWorkflowHistory.ACTION_ACCOUNTING_APPROVED,
                label="Cleared for Payment",
                details=f"Approved by {acting_user.get_full_name() or acting_user.username}.",
                actor=acting_user,
                occurred_at=timezone.now(),
                idempotency_key=str(receiving_id),
            )

            # Refresh to return updated state
            receiving.refresh_from_db()
            return receiving

    @classmethod
    def send_to_coo(cls, receiving_id: int, acting_user):
        """
        Send a receiving to the COO for approval (oversupply / variance scenario).

        UNDER_REVIEW → PENDING_COO

        Raises:
            ReceivingNotFoundError
            InvalidStatusTransitionError
        """
        with transaction.atomic():
            try:
                receiving = (
                    Receiving.objects
                    .select_for_update()
                    .get(pk=receiving_id)
                )
            except Receiving.DoesNotExist:
                raise ReceivingNotFoundError(
                    f"Receiving {receiving_id} does not exist."
                )

            if receiving.status not in cls.VALID_FROM_SEND_TO_COO:
                raise InvalidStatusTransitionError(
                    f"Cannot send to COO: receiving is in status "
                    f"{receiving.status!r}.",
                    current_status=receiving.status,
                    target_status=Receiving.PENDING_COO,
                )

            receiving.status = Receiving.PENDING_COO
            receiving.sent_to_coo_by = acting_user
            receiving.sent_to_coo_at = timezone.now()
            receiving.save(update_fields=["status", "sent_to_coo_by", "sent_to_coo_at"])

            ReceivingWorkflowHistory.objects.create_event(
                receiving=receiving,
                action_type=ReceivingWorkflowHistory.ACTION_SENT_TO_COO,
                label="Sent to COO",
                details=f"Sent for approval by {acting_user.get_full_name() or acting_user.username}.",
                actor=acting_user,
                occurred_at=timezone.now(),
                idempotency_key=str(receiving_id),
            )

            receiving.refresh_from_db()
            return receiving

    @classmethod
    def approve_coo(cls, receiving_id: int, acting_user):
        """
        COO approves a receiving.

        PENDING_COO → REVIWED

        Raises:
            ReceivingNotFoundError
            InvalidStatusTransitionError
        """
        with transaction.atomic():
            try:
                receiving = (
                    Receiving.objects
                    .select_for_update()
                    .get(pk=receiving_id)
                )
            except Receiving.DoesNotExist:
                raise ReceivingNotFoundError(
                    f"Receiving {receiving_id} does not exist."
                )

            if receiving.status not in cls.VALID_FROM_APPROVE_COO:
                raise InvalidStatusTransitionError(
                    f"Cannot approve as COO: receiving is in status "
                    f"{receiving.status!r}, expected {Receiving.PENDING_COO!r}.",
                    current_status=receiving.status,
                    target_status=Receiving.REVIWED,
                )

            receiving.status = Receiving.REVIWED
            receiving.coo_decision_by = acting_user
            receiving.coo_decision_at = timezone.now()
            receiving.save(update_fields=["status", "coo_decision_by", "coo_decision_at"])

            # Create pending payment
            po = receiving.purchase_order
            Payment.objects.get_or_create(
                purchase_order=po,
                defaults={
                    "status": Payment.PENDING,
                    "created_by": acting_user,
                },
            )

            # Post stock
            record_receiving_as_stock(receiving.pk, acting_user.pk)

            ReceivingWorkflowHistory.objects.create_event(
                receiving=receiving,
                action_type=ReceivingWorkflowHistory.ACTION_COO_APPROVED,
                label="COO Approved",
                details=f"Approved by {acting_user.get_full_name() or acting_user.username}.",
                actor=acting_user,
                occurred_at=timezone.now(),
                idempotency_key=str(receiving_id),
            )

            receiving.refresh_from_db()
            return receiving

    @classmethod
    def deny_accounting(cls, receiving_id: int, acting_user, reason: str):
        """
        Accounting denies a receiving (with a reason).

        Raises:
            ReceivingNotFoundError
            InvalidStatusTransitionError
        """
        with transaction.atomic():
            try:
                receiving = (
                    Receiving.objects
                    .select_for_update()
                    .get(pk=receiving_id)
                )
            except Receiving.DoesNotExist:
                raise ReceivingNotFoundError(
                    f"Receiving {receiving_id} does not exist."
                )

            if receiving.status not in cls.VALID_FROM_DENY_ACCOUNTING:
                raise InvalidStatusTransitionError(
                    f"Cannot deny as accounting: receiving is in status "
                    f"{receiving.status!r}.",
                    current_status=receiving.status,
                    target_status=Receiving.DENIED,
                )

            receiving.status = Receiving.DENIED
            receiving.reviewed_by = acting_user
            receiving.reviewed_at = timezone.now()
            receiving.save(update_fields=[
                "status",
                "reviewed_by",
                "reviewed_at",
            ])

            ReceivingWorkflowHistory.objects.create_event(
                receiving=receiving,
                action_type=ReceivingWorkflowHistory.ACTION_ACCOUNTING_DENIED,
                label="Accounting Denied",
                details=reason,
                actor=acting_user,
                occurred_at=timezone.now(),
                idempotency_key=str(receiving_id),
            )

            receiving.refresh_from_db()
            return receiving

    @classmethod
    def deny_coo(cls, receiving_id: int, acting_user, reason: str):
        """
        COO denies a receiving (with a reason).

        Raises:
            ReceivingNotFoundError
            InvalidStatusTransitionError
        """
        with transaction.atomic():
            try:
                receiving = (
                    Receiving.objects
                    .select_for_update()
                    .get(pk=receiving_id)
                )
            except Receiving.DoesNotExist:
                raise ReceivingNotFoundError(
                    f"Receiving {receiving_id} does not exist."
                )

            if receiving.status not in cls.VALID_FROM_DENY_COO:
                raise InvalidStatusTransitionError(
                    f"Cannot deny as COO: receiving is in status "
                    f"{receiving.status!r}.",
                    current_status=receiving.status,
                    target_status=Receiving.DENIED,
                )

            receiving.status = Receiving.DENIED
            receiving.coo_decision_by = acting_user
            receiving.coo_decision_at = timezone.now()
            receiving.save(update_fields=[
                "status",
                "coo_decision_by",
                "coo_decision_at",
            ])

            ReceivingWorkflowHistory.objects.create_event(
                receiving=receiving,
                action_type=ReceivingWorkflowHistory.ACTION_COO_DENIED,
                label="COO Denied",
                details=reason,
                actor=acting_user,
                occurred_at=timezone.now(),
                idempotency_key=str(receiving_id),
            )

            receiving.refresh_from_db()
            return receiving
