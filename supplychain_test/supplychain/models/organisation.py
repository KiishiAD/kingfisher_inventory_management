from django.conf import settings
from django.db import models
from django.utils import timezone


class Organisation(models.Model):
    """Top-level tenant container for multi-tenancy."""
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class OrganisationMembership(models.Model):
    """Maps a user to an organisation with a role."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    organisation = models.ForeignKey(
        Organisation,
        on_delete=models.CASCADE,
    )
    role = models.CharField(max_length=100)

    class Meta:
        unique_together = [["user", "organisation"]]

    def __str__(self):
        return f"{self.user} is {self.role} of {self.organisation}"
