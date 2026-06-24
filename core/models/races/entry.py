from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models

from core.models import Car
from core.models.championship import ChampionshipEntry
from core.models.choices import RaceEntryStatus
from core.models.races.race import Race

User = get_user_model()


class RaceEntry(models.Model):
    """
    Represents a participant's entry in a specific race.

    Can be:
    - Linked to a ChampionshipEntry (championship race)
    - Standalone (no championship) with team or user directly
    """

    race = models.ForeignKey(
        Race,
        on_delete=models.CASCADE,
        related_name="entries",
    )

    # Championship context (optional)
    championship_entry = models.ForeignKey(
        ChampionshipEntry,
        on_delete=models.CASCADE,
        related_name="race_entries",
        null=True,
        blank=True,
    )

    # Standalone context (mutually exclusive with championship_entry)
    team = models.ForeignKey(
        "Team",
        on_delete=models.CASCADE,
        related_name="race_entries",
        null=True,
        blank=True,
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="race_entries",
        null=True,
        blank=True,
    )

    # Required for standalone, inherited from ChampionshipEntry otherwise
    car = models.ForeignKey(
        Car,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    racing_number = models.IntegerField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=RaceEntryStatus.choices,
        default=RaceEntryStatus.PENDING,
    )

    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_race_entries",
    )

    ban_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "RaceEntry"
        verbose_name_plural = "RaceEntries"
        ordering = ["racing_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["race", "championship_entry"],
                condition=models.Q(championship_entry__isnull=False),
                name="unique_championship_entry_per_race",
            ),
            models.UniqueConstraint(
                fields=["race", "team"],
                condition=models.Q(team__isnull=False, championship_entry__isnull=True),
                name="unique_team_per_standalone_race",
            ),
            models.UniqueConstraint(
                fields=["race", "user"],
                condition=models.Q(user__isnull=False, championship_entry__isnull=True),
                name="unique_user_per_standalone_race",
            ),
        ]

    def clean(self):
        errors = {}

        if self.championship_entry:
            # Championship context — team/user/car/racing_number not needed
            if self.team or self.user:
                errors["team"] = (
                    "Cannot specify team or user when championship_entry is set."
                )
            if self.car or self.racing_number:
                errors["car"] = (
                    "Cannot specify car or racing_number when championship_entry is set."
                )
        else:
            # Standalone context
            if self.team and self.user:
                errors["team"] = "Cannot have both team and user."
            if not self.team and not self.user:
                errors["team"] = (
                    "Must specify either team, user, or championship_entry."
                )
            if not self.car:
                errors["car"] = "Car is required for standalone race entries."
            if not self.racing_number:
                errors["racing_number"] = (
                    "Racing number is required for standalone race entries."
                )

        if errors:
            raise ValidationError(errors)

    def accept(self, resolved_by):
        if self.status == RaceEntryStatus.BANNED:
            raise ValidationError("Cannot accept a banned entry.")
        self.status = RaceEntryStatus.APPROVED
        self.resolved_by = resolved_by
        self.save()

    def reject(self, resolved_by):
        if self.status == RaceEntryStatus.BANNED:
            raise ValidationError("Cannot reject a banned entry.")
        self.status = RaceEntryStatus.REJECTED
        self.resolved_by = resolved_by
        self.save()

    def ban(self, reason=""):
        self.status = RaceEntryStatus.BANNED
        self.ban_reason = reason
        self.save()