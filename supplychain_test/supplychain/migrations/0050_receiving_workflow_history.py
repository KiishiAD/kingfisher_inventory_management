"""
Migration: Create ReceivingWorkflowHistory model.

Adds an append-only client-facing event log for Receiving records,
with idempotent event creation and hidden side-effect metadata.
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("supplychain", "0049_alter_requisition_evidence"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReceivingWorkflowHistory",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "action_type",
                    models.CharField(
                        choices=[
                            ("CREATED", "Created"),
                            ("GOODS_RECEIVED", "Goods Received"),
                            ("ACCOUNTING_APPROVED", "Accounting Approved"),
                            ("ACCOUNTING_DENIED", "Accounting Denied"),
                            ("SENT_TO_COO", "Sent to COO"),
                            ("COO_APPROVED", "COO Approved"),
                            ("COO_DENIED", "COO Denied"),
                        ],
                        max_length=30,
                    ),
                ),
                (
                    "label",
                    models.CharField(max_length=255),
                ),
                (
                    "details",
                    models.TextField(blank=True, default=""),
                ),
                (
                    "actor_display",
                    models.CharField(default="", max_length=255),
                ),
                (
                    "occurred_at",
                    models.DateTimeField(),
                ),
                (
                    "idempotency_key",
                    models.CharField(max_length=100),
                ),
                (
                    "metadata",
                    models.JSONField(blank=True, default=dict),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="receiving_workflow_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "receiving",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="workflow_history",
                        to="supplychain.receiving",
                    ),
                ),
            ],
            options={
                "verbose_name": "Receiving Workflow History",
                "verbose_name_plural": "Receiving Workflow Histories",
                "ordering": ["occurred_at", "pk"],
            },
        ),
        migrations.AddConstraint(
            model_name="receivingworkflowhistory",
            constraint=models.UniqueConstraint(
                fields=("receiving", "action_type", "idempotency_key"),
                name="unique_receiving_action_idempotency",
            ),
        ),
    ]
