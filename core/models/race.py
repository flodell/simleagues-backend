import secrets
from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from core.models.championship import Championship, Driver, Team
from core.models.choices import RaceVisibility, RaceStatus, ParticipantType
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

    # Results entry tracking
    entered_by = models.ForeignKey(
        Driver,
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
    def is_league_race(self):
        """Check if race belongs to a league."""
        return self.league is not None

    @property
    def is_championship_race(self):
        """Check if race is part of a championship."""
        return self.championship is not None

    @property
    def is_independent(self):
        """Check if race is independent (no league, no championship)."""
        return self.league is None and self.championship is None

    @property
    def result_count(self):
        """Get number of results entered for this race."""
        return self.results.count()

    @property
    def is_completed(self):
        """Check if race is completed."""
        return self.status == RaceStatus.COMPLETED

    @property
    def has_results(self):
        """Check if race has any results."""
        return self.results.exists()

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
        """
        Check if user can enter results for this race.

        Args:
            user: User to check

        Returns:
            bool: True if user can enter results
        """
        # Creator can always enter
        if self.creator == user:
            return True

        # League staff can enter for league races
        if self.league:
            return self.league.is_staff(user)

        return False

    def can_user_participate(self, user):
        """
        Check if user can participate in this race.

        Args:
            user: User to check

        Returns:
            bool: True if user can participate
        """
        # For championship races, must be registered participant
        if self.championship:
            return self.championship.participants.filter(driver=user).exists()

        # For league races, must be league member
        if self.league:
            return self.league.is_member(user)

        # For independent races, anyone can participate
        return True

    def get_winner(self):
        """
        Get the winner of the race (position 1).

        Returns:
            RaceResult or None
        """
        return self.results.filter(position=1).first()

    def get_podium(self):
        """
        Get the podium finishers (positions 1-3).

        Returns:
            QuerySet of RaceResult
        """
        return self.results.filter(position__lte=3).order_by("position")


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

    # Driver reference (always required)
    driver = models.ForeignKey(
        Driver,
        on_delete=models.CASCADE,
        related_name="race_results",
        help_text="Driver who achieved this result",
    )

    # Team (for TEAM championship only)
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="team_race_results",
        null=True,
        blank=True,
        help_text="Team this result belongs to (only for TEAM championship)",
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
                fields=["race", "driver"], name="unique_driver_per_race"
            ),
            # For TEAM: team unique per race
            models.UniqueConstraint(
                fields=["race", "team"],
                condition=models.Q(team__isnull=False),
                name="unique_team_per_race",
            ),
        ]

    def clean(self):

        # DNF and DSQ cannot both be true
        if self.dnf and self.dsq:
            raise ValidationError(
                {
                    "dnf": "Cannot be both DNF and DSQ.",
                    "dsq": "Cannot be both DNF and DSQ.",
                }
            )

        # For championship races: driver must be registered participant
        if self.race.is_championship_race:
            if self.race.championship.participant_type == ParticipantType.TEAM:
                # Must have team
                if not self.team:
                    raise ValidationError(
                        {"team": "Team is required for team championship races."}
                    )

                # User must be member of the team
                if not self.team.members.filter(driver=self.driver).exists():
                    raise ValidationError(
                        {"driver": "Driver must be a member of the specified team."}
                    )

            else:
                # INDIVIDUAL Must NOT have team
                if self.team:
                    raise ValidationError(
                        {"team": "Individual championship races cannot have teams."}
                    )
        # For league races: driver must be league member
        if self.race.league:
            if not self.race.league.is_member(self.driver):
                raise ValidationError(
                    {"driver": "Driver must be a member of the league."}
                )
