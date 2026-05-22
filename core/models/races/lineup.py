from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models

from core.models.races.entry import RaceEntry
from core.models.races.race import Race
from core.models.team import TeamMembership

User = get_user_model()


class RaceLineup(models.Model):
    """
    Represents a driver's lineup for a team race entry.

    Only used for team races (championship or standalone).
    Driver must be an active member of the team.
    """

    race = models.ForeignKey(
        Race,
        on_delete=models.CASCADE,
        related_name="lineups",
    )

    race_entry = models.ForeignKey(
        RaceEntry,
        on_delete=models.CASCADE,
        related_name="lineups",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "RaceLineup"
        verbose_name_plural = "RaceLineups"
        ordering = ["race"]

    def clean(self):
        errors = {}

        team = self.race_entry.team or (
            self.race_entry.championship_entry
            and self.race_entry.championship_entry.team
        )
        if not team:
            errors["race_entry"] = "RaceLineup can only be used for team race entries."

        if errors:
            raise ValidationError(errors)


class RaceLineupDriver(models.Model):
    """
    Represents a driver in a race lineup.
    Driver must be an active member of the team.
    """

    lineup = models.ForeignKey(
        RaceLineup,
        on_delete=models.CASCADE,
        related_name="lineup_drivers",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="race_lineup_entries",
    )
    role = models.CharField(
        max_length=100,
        blank=True,
        help_text="Driver category/role (e.g. Pro, Am, Silver, Gold)",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "RaceLineupDriver"
        verbose_name_plural = "RaceLineupDrivers"
        unique_together = [["lineup", "user"]]

    def clean(self):
        errors = {}

        team = self.lineup.race_entry.team or (
            self.lineup.race_entry.championship_entry
            and self.lineup.race_entry.championship_entry.team
        )

        if (
            team
            and not TeamMembership.objects.filter(
                team=team, user=self.user, is_active=True
            ).exists()
        ):
            errors["user"] = (
                f"{self.user.username} is not an active member of {team.name}."
            )

        if errors:
            raise ValidationError(errors)