from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models

from core.models.car import Car
from core.models.choices import ParticipantType, ChampionshipStatus

User = get_user_model()


class Championship(models.Model):
    """
    Represents a racing championship within a league.

    A championship is a series of races with a specific ruleset
    and point system. Leagues can have multiple championship.
    """

    # League reference
    league = models.ForeignKey(
        "League",
        on_delete=models.CASCADE,
        related_name="championships",
    )

    # Basic Information
    name = models.CharField(
        max_length=200,
        help_text="Championship name (e.g., '2025 Season 1', 'Winter Cup')",
    )

    season = models.CharField(
        max_length=50,
        blank=True,
        help_text="Season identifier (e.g., '2025', 'Winter 2025')",
    )

    description = models.TextField(
        blank=True,
    )

    # Dates
    start_date = models.DateField()

    end_date = models.DateField(
        null=True,
        blank=True,
    )

    # Championship Type
    participant_type = models.CharField(
        max_length=20,
        choices=ParticipantType.choices,
        default=ParticipantType.INDIVIDUAL,
    )

    # Team Configuration (only for TEAM championship)
    min_drivers_per_team = models.IntegerField(
        null=True,
        blank=True,
        default=1,
    )

    max_drivers_per_team = models.IntegerField(
        null=True,
        blank=True,
        default=3,
    )

    # Rules and Configuration
    point_system = models.JSONField(
        default=dict,
        help_text="Point system as JSON (e.g., {'1': 25, '2': 18, '3': 15, ...})",
    )

    allowed_car_categories = models.JSONField(
        default=list,
        blank=True,
        help_text="Allowed car categories as JSON array (e.g., ['HYPERCAR', 'LMP2'])",
    )

    max_participants = models.IntegerField(
        null=True,
        blank=True,
        help_text="Maximum number of participants (teams or drivers)",
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=ChampionshipStatus.choices,
        default=ChampionshipStatus.UPCOMING,
        help_text="Current championship status",
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Championship"
        verbose_name_plural = "Championships"
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.league.name} - {self.name}"

    def clean(self):
        """Validate team driver limits."""

        if self.participant_type == ParticipantType.TEAM:
            if self.min_drivers_per_team and self.max_drivers_per_team:
                if self.min_drivers_per_team > self.max_drivers_per_team:
                    raise ValidationError(
                        {
                            "min_drivers_per_team": "Minimum cannot be greater than maximum."
                        }
                    )

            if self.min_drivers_per_team and self.min_drivers_per_team < 1:
                raise ValidationError(
                    {"min_drivers_per_team": "Minimum must be at least 1."}
                )

    @property
    def completed_race_count(self):
        """Get number of completed races."""
        return self.races.filter(status="COMPLETED").count()

    def get_default_point_system(self):
        """
        Get default FIA WEC point system.

        Returns:
            dict: Default point system
        """
        return {
            "1": 25,
            "2": 18,
            "3": 15,
            "4": 12,
            "5": 10,
            "6": 8,
            "7": 6,
            "8": 4,
            "9": 2,
            "10": 1,
        }


class Driver(models.Model):
    """
    Represents a driver participating in a championship.

    Can be either:
    - Individual driver (team=None)
    - Team member (team=Team)
    """

    championship = models.ForeignKey(
        Championship,
        on_delete=models.CASCADE,
        related_name="participants",
        help_text="Championship this participant is registered in",
    )

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="participations"
    )

    # Team reference (optional - only for team championship)
    team = models.ForeignKey(
        "Team",
        on_delete=models.CASCADE,
        related_name="members",
        null=True,
        blank=True,
        help_text="Team this driver belongs to (only for team championship)",
    )

    car = models.ForeignKey(
        Car, on_delete=models.PROTECT, help_text="Car used by this driver/team"
    )

    racing_number = models.IntegerField(help_text="Driver or team racing number")

    # Driver role (for team championship)
    role = models.CharField(
        max_length=100,
        blank=True,
        help_text="Driver role in team (e.g., 'Pro', 'Am', 'Silver', 'Gold'). Only for team championship.",
    )

    # Metadata
    joined_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Driver"
        verbose_name_plural = "Drivers"
        unique_together = [["championship", "user"], ["championship", "racing_number"]]
        ordering = ["racing_number"]

    def __str__(self):
        if self.team:
            return f"#{self.racing_number} {self.user.username} ({self.team.name})"
        return f"#{self.racing_number} {self.user.username}"

    def clean(self):
        """Validate participant based on championship type."""

        # Team championship: must have a team
        if self.championship.participant_type == ParticipantType.TEAM:
            if not self.team:
                raise ValidationError(
                    {"team": "Team is required for team championship."}
                )

            # Check if driver is already in another team in this championship
            existing_in_other_team = Driver.objects.filter(
                championship=self.championship, user=self.user, team__isnull=False
            ).exclude(pk=self.pk)

            if existing_in_other_team.exists():
                other_team = existing_in_other_team.first().team
                raise ValidationError(
                    {
                        "driver": f'Driver is already in team "{other_team.name}" for this championship.'
                    }
                )

        # Individual championship: must NOT have a team
        if self.championship.participant_type == ParticipantType.INDIVIDUAL:
            if self.team:
                raise ValidationError(
                    {"team": "Individual championship cannot have teams."}
                )

    @property
    def is_team_member(self):
        return self.team is not None


class Standing(models.Model):
    """
    Championship standing entry.

    Can represent either:
    - Driver standing (for INDIVIDUAL championship)
    - Team standing (for TEAM championship)
    """

    championship = models.ForeignKey(
        Championship,
        on_delete=models.CASCADE,
        related_name="standings",
        help_text="Championship this standing belongs to",
    )

    # Either driver OR team (mutually exclusive)
    driver = models.ForeignKey(
        Driver,
        on_delete=models.CASCADE,
        related_name="standings",
        null=True,
        blank=True,
        help_text="Driver (only for INDIVIDUAL championship)",
    )

    team = models.ForeignKey(
        "Team",
        on_delete=models.CASCADE,
        related_name="standings",
        null=True,
        blank=True,
        help_text="Team (only for TEAM championship)",
    )

    # Current position
    position = models.IntegerField(
        default=0, help_text="Current position in championship"
    )

    # Aggregated stats
    total_points = models.IntegerField(default=0, help_text="Total championship points")

    races_completed = models.IntegerField(
        default=0, help_text="Number of races completed"
    )

    wins = models.IntegerField(default=0, help_text="Number of race wins (P1)")

    podiums = models.IntegerField(
        default=0, help_text="Number of podium finishes (P1-P3)"
    )

    fastest_laps = models.IntegerField(default=0, help_text="Number of fastest laps")

    dnf_count = models.IntegerField(
        default=0, verbose_name="DNF count", help_text="Number of DNFs (Did Not Finish)"
    )

    dsq_count = models.IntegerField(
        default=0, verbose_name="DSQ count", help_text="Number of disqualifications"
    )

    # Best result
    best_finish = models.IntegerField(
        null=True, blank=True, help_text="Best finishing position in this championship"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Standing"
        verbose_name_plural = "Standings"
        ordering = ["championship", "-total_points"]
        constraints = [
            # For INDIVIDUAL championship: unique driver per championship
            models.UniqueConstraint(
                fields=["championship", "driver"],
                condition=models.Q(driver__isnull=False),
                name="unique_driver_standing_per_championship",
            ),
            # For TEAM championship: unique team per championship
            models.UniqueConstraint(
                fields=["championship", "team"],
                condition=models.Q(team__isnull=False),
                name="unique_team_standing_per_championship",
            ),
        ]

    def clean(self):
        """Validate standing based on championship type."""

        # Must have exactly one: driver OR team
        if not self.driver and not self.team:
            raise ValidationError(
                {
                    "driver": "Must specify either driver or team.",
                    "team": "Must specify either driver or team.",
                }
            )

        if self.driver and self.team:
            raise ValidationError(
                {
                    "driver": "Cannot have both driver and team.",
                    "team": "Cannot have both driver and team.",
                }
            )

        # Validate based on championship type
        if self.championship.participant_type == ParticipantType.INDIVIDUAL:
            if not self.driver:
                raise ValidationError(
                    {"driver": "Individual championship require a driver."}
                )
            if self.team:
                raise ValidationError(
                    {"team": "Individual championship cannot have teams."}
                )

        if self.championship.participant_type == ParticipantType.TEAM:
            if not self.team:
                raise ValidationError({"team": "Team championship require a team."})
            if self.driver:
                raise ValidationError(
                    {"driver": "Team championship cannot have individual drivers."}
                )
