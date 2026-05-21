import secrets
from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from core.models import Car
from core.models.championship import Championship, ChampionshipEntry
from core.models.choices import (
    RaceVisibility,
    RaceStatus,
    ParticipantType,
    RaceEntryStatus,
)
from core.models.league import League
from core.models.team import TeamMembership
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
    name = models.CharField(
        max_length=200,
    )

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
        blank=True, help_text="Optional notes about the race (incidents, weather, etc.)"
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
        from django.core.exceptions import ValidationError

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
        """Check if race is part of a championship."""
        return self.championship is not None

    @property
    def is_independent(self):
        """Check if race is independent (no league, no championship)."""
        return self.league is None and self.championship is None

    def can_user_view(self, user):
        """
        Check if user can view this race.

        Args:
            user: User to check

        Returns:
            bool: True if user can view
        """
        if self.creator == user or self.visibility == RaceVisibility.PUBLIC:
            return True

        if self.visibility == RaceVisibility.UNLISTED:
            # Need invitation code OR be league member
            if self.league and self.league.is_member(user):
                return True
            return False  # Need code for unlisted

        if self.visibility == RaceVisibility.PRIVATE:
            # Must be league member
            if self.league:
                return self.league.is_member(user)
            # If no league, only creator
            return False

        return False

    def can_user_enter_results(self, user):
        # Creator can always enter
        if self.creator == user:
            return True

        # League staff can enter for league races
        if self.league:
            return self.league.is_staff(user)

        return False

    def can_user_participate(self, user):

        # For championship races, must be registered participant
        if self.championship:
            # Must have an approved RaceEntry linked to a ChampionshipEntry for this user
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


class RaceResult(models.Model):
    """
    Represents a driver's result in a race.

    Works for both championship and standalone races.
    """

    # Race reference
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
    fastest_lap = models.BooleanField(
        default=False,
    )

    dnf = models.BooleanField(default=False, verbose_name="DNF")
    dsq = models.BooleanField(default=False, verbose_name="DSQ")

    # Points (only for championship races)
    points = models.IntegerField(
        default=0, help_text="Championship points earned (only for championship races)"
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
            # Position must be unique per race
            models.UniqueConstraint(
                fields=["race", "position"], name="unique_position_per_race"
            ),
            # Driver must be unique per race
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
