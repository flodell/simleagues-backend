import secrets

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models

from core.models.championship import Championship
from core.models.choices import RaceStatus, RaceVisibility
from core.models.league import League
from core.models.track import Track

User = get_user_model()


class Race(models.Model):
    """
    Represents a single race.

    Can be:
    - Part of a league championship: league + championship
    - Part of a league (standalone): league only
    - Independent: no league, no championship

    Each race has its own visibility level independent of league.
    """

    # League reference (optional)
    league = models.ForeignKey(
        League,
        on_delete=models.CASCADE,
        related_name="races",
        null=True,
        blank=True,
        help_text="League this race belongs to (optional)",
    )

    # Championship reference (optional, requires league)
    championship = models.ForeignKey(
        Championship,
        on_delete=models.CASCADE,
        related_name="races",
        null=True,
        blank=True,
        help_text="Championship this race belongs to (optional)",
    )

    # Creator (required)
    creator = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="created_races",
        help_text="Race creator",
    )

    # Basic Information
    name = models.CharField(max_length=200)

    round_number = models.IntegerField(
        null=True,
        blank=True,
        help_text="Race round number (only for championship races)",
    )

    # Track reference
    track = models.ForeignKey(
        Track,
        on_delete=models.PROTECT,
        help_text="Track where this race takes place",
    )

    # Schedule
    scheduled_date = models.DateTimeField(
        help_text="Scheduled date and time of the race"
    )

    # Race Configuration
    duration_minutes = models.IntegerField(
        null=True,
        blank=True,
        help_text="Race duration in minutes (e.g., 360 for 6 hours)",
    )

    laps = models.IntegerField(
        null=True,
        blank=True,
        help_text="Number of laps (if race is by laps instead of time)",
    )

    # Visibility (independent of league)
    visibility = models.CharField(
        max_length=20,
        choices=RaceVisibility.choices,
        default=RaceVisibility.PUBLIC,
        help_text="Race visibility level",
    )

    invitation_code = models.CharField(
        max_length=32,
        unique=True,
        blank=True,
        null=True,
        help_text="Invitation code for UNLISTED races",
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=RaceStatus.choices,
        default=RaceStatus.SCHEDULED,
    )

    # User who entered the results
    entered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entered_races",
        help_text="User who entered the results",
    )

    entered_at = models.DateTimeField(
        null=True, blank=True, help_text="When results were entered"
    )

    # Optional race notes
    notes = models.TextField(
        blank=True,
        help_text="Optional notes about the race (incidents, weather, etc.)",
    )

    is_active = models.BooleanField(default=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Race"
        verbose_name_plural = "Races"
        ordering = ["-scheduled_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["championship", "round_number"],
                condition=models.Q(
                    championship__isnull=False, round_number__isnull=False
                ),
                name="unique_round_per_championship",
            )
        ]

    def __str__(self):
        if self.championship:
            return f"{self.championship.name} - Round {self.round_number}: {self.track.name}"
        elif self.league:
            return f"{self.league.name} - {self.name}"
        return self.name

    def save(self, *args, **kwargs):
        if self.visibility == RaceVisibility.UNLISTED and not self.invitation_code:
            self.invitation_code = secrets.token_urlsafe(16)
        super().save(*args, **kwargs)

    def clean(self):
        """Validate race configuration."""
        # Championship requires league
        if self.championship and not self.league:
            raise ValidationError(
                {"championship": "Championship races must belong to a league."}
            )

        # Championship must match league
        if self.championship and self.league:
            if self.championship.league != self.league:
                raise ValidationError(
                    {"championship": "Championship must belong to the same league."}
                )

        # Championship races need round_number
        if self.championship and not self.round_number:
            raise ValidationError(
                {"round_number": "Round number is required for championship races."}
            )

        # Non-championship races should not have round_number
        if not self.championship and self.round_number:
            raise ValidationError(
                {
                    "round_number": "Round number should only be set for championship races."
                }
            )

        # Private league races cannot be public
        if self.league and self.league.visibility == "PRIVATE":
            if self.visibility == RaceVisibility.PUBLIC:
                raise ValidationError(
                    {"visibility": "Races in private leagues cannot be public."}
                )

    @property
    def is_championship_race(self):
        return self.championship is not None

    @property
    def is_independent(self):
        return self.league is None and self.championship is None

    def can_user_view(self, user):
        if self.creator == user or self.visibility == RaceVisibility.PUBLIC:
            return True

        if self.visibility == RaceVisibility.UNLISTED:
            if self.league and self.league.is_member(user):
                return True
            return False

        if self.visibility == RaceVisibility.PRIVATE:
            if self.league:
                return self.league.is_member(user)
            return False

        return False

    def can_user_enter_results(self, user):
        if self.creator == user:
            return True
        if self.league:
            return self.league.is_staff(user)
        return False

    def can_user_participate(self, user):
        from core.models.choices import RaceEntryStatus

        # For championship races, must be registered participant
        if self.championship:
            return (
                self.entries.filter(
                    championship_entry__user=user,
                    status=RaceEntryStatus.APPROVED,
                ).exists()
                or self.entries.filter(
                    championship_entry__team__memberships__user=user,
                    championship_entry__team__memberships__is_active=True,
                    status=RaceEntryStatus.APPROVED,
                ).exists()
            )

        # For league races, must be league member
        if self.league:
            return self.league.is_member(user)

        # For independent races, anyone can participate
        return True