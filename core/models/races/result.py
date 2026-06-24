from django.core.exceptions import ValidationError
from django.db import models

from core.models.races.entry import RaceEntry
from core.models.races.race import Race


class RaceResult(models.Model):
    """
    Represents a driver's result in a race.

    Works for both championship and standalone races.
    """

    race = models.ForeignKey(
        Race,
        on_delete=models.CASCADE,
        related_name="results",
        help_text="Race this result belongs to",
    )

    race_entry = models.ForeignKey(
        RaceEntry,
        on_delete=models.CASCADE,
        related_name="results",
    )

    # Result data
    position = models.PositiveIntegerField()

    # Time/Performance data
    total_time = models.DurationField(
        null=True, blank=True, help_text="Total race time (for time-based races)"
    )

    laps_completed = models.IntegerField(
        null=True, blank=True, help_text="Number of laps completed"
    )

    fastest_lap_time = models.DurationField(
        null=True, blank=True, help_text="Fastest lap time during the race"
    )

    # Flags
    fastest_lap = models.BooleanField(default=False)
    dnf = models.BooleanField(default=False, verbose_name="DNF")
    dsq = models.BooleanField(default=False, verbose_name="DSQ")

    # Points (only for championship races)
    points = models.IntegerField(
        default=0,
        help_text="Championship points earned (only for championship races)",
    )

    # Optional notes
    notes = models.TextField(
        blank=True, help_text="Optional notes (incidents, penalties, etc.)"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Race Result"
        verbose_name_plural = "Race Results"
        ordering = ["race", "position"]
        constraints = [
            models.UniqueConstraint(
                fields=["race", "position"], name="unique_position_per_race"
            ),
            models.UniqueConstraint(
                fields=["race", "race_entry"], name="unique_driver_per_race"
            ),
        ]

    def clean(self):
        errors = {}

        if self.dnf and self.dsq:
            errors["dnf"] = "Cannot be both DNF and DSQ."

        # RaceEntry must belong to this race
        if self.race_entry.race != self.race:
            errors["race_entry"] = "RaceEntry does not belong to this race."

        if errors:
            raise ValidationError(errors)