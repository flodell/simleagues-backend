from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class ChampionshipStatus(models.TextChoices):
    UPCOMING = 'UPCOMING', 'Upcoming'
    ACTIVE = 'ACTIVE', 'Active'
    COMPLETED = 'COMPLETED', 'Completed'
    CANCELLED = 'CANCELLED', 'Cancelled'


class ParticipantType(models.TextChoices):
    TEAM = 'TEAM', 'Team'
    INDIVIDUAL = 'INDIVIDUAL', 'Individual'


class Championship(models.Model):
    """
    Represents a racing championship within a league.

    A championship is a series of races with a specific ruleset
    and point system. Leagues can have multiple championships.
    """

    # League reference
    league = models.ForeignKey(
        'leagues.League',
        on_delete=models.CASCADE,
        related_name='championships',
    )

    # Basic Information
    name = models.CharField(
        max_length=200,
        help_text="Championship name (e.g., '2025 Season 1', 'Winter Cup')"
    )

    season = models.CharField(
        max_length=50,
        blank=True,
        help_text="Season identifier (e.g., '2025', 'Winter 2025')"
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

    # Team Configuration (only for TEAM championships)
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
        help_text="Point system as JSON (e.g., {'1': 25, '2': 18, '3': 15, ...})"
    )

    allowed_car_categories = models.JSONField(
        default=list,
        blank=True,
        help_text="Allowed car categories as JSON array (e.g., ['HYPERCAR', 'LMP2'])"
    )

    max_participants = models.IntegerField(
        null=True,
        blank=True,
        help_text="Maximum number of participants (teams or drivers)"
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=ChampionshipStatus.choices,
        default=ChampionshipStatus.UPCOMING,
        help_text="Current championship status"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Championship'
        verbose_name_plural = 'Championships'
        ordering = ['-start_date']


    def __str__(self):
        return f"{self.league.name} - {self.name}"

    def clean(self):
        """Validate team driver limits."""
        from django.core.exceptions import ValidationError

        if self.participant_type == ParticipantType.TEAM:
            if self.min_drivers_per_team and self.max_drivers_per_team:
                if self.min_drivers_per_team > self.max_drivers_per_team:
                    raise ValidationError({
                        'min_drivers_per_team': 'Minimum cannot be greater than maximum.'
                    })

            if self.min_drivers_per_team and self.min_drivers_per_team < 1:
                raise ValidationError({
                    'min_drivers_per_team': 'Minimum must be at least 1.'
                })

    @property
    def race_count(self):
        """Get total number of races."""
        return self.races.count()

    @property
    def completed_race_count(self):
        """Get number of completed races."""
        return self.races.filter(status='COMPLETED').count()

    @property
    def participant_count(self):
        return self.participants.count()

    @property
    def team_count(self):
        if self.participant_type == ParticipantType.TEAM:
            return self.teams.count()
        return 0


    def get_default_point_system(self):
        """
        Get default FIA WEC point system.

        Returns:
            dict: Default point system
        """
        return {
            '1': 25, '2': 18, '3': 15, '4': 12, '5': 10,
            '6': 8, '7': 6, '8': 4, '9': 2, '10': 1
        }


class Team(models.Model):
    """
    Represents a racing team in a championship.

    A team can have multiple drivers competing together.
    """

    championship = models.ForeignKey(
        Championship,
        on_delete=models.CASCADE,
        related_name='teams',
    )

    # Team Information
    name = models.CharField(
        max_length=200,
    )

    racing_number = models.IntegerField(
    )

    car = models.ForeignKey(
        'cars.Car',
        on_delete=models.PROTECT,
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Team'
        verbose_name_plural = 'Teams'
        unique_together = [
            ['championship', 'name'],
            ['championship', 'racing_number']
        ]
        ordering = ['racing_number']


    def __str__(self):
        return f"#{self.racing_number} {self.name}"

    @property
    def driver_count(self):
        return self.members.count()

    @property
    def is_valid_driver_count(self):
        """
        Check if team has valid number of drivers.

        Returns:
            tuple: (is_valid: bool, message: str)
        """
        count = self.driver_count

        min_drivers = self.championship.min_drivers_per_team or 1
        max_drivers = self.championship.max_drivers_per_team

        if count < min_drivers:
            return False, f"Need at least {min_drivers} driver(s)"

        if max_drivers and count > max_drivers:
            return False, f"Cannot exceed {max_drivers} driver(s)"

        return True, "Valid"

    def can_add_driver(self):
        """
        Check if team can add more drivers.

        Returns:
            tuple: (can_add: bool, message: str)
        """
        max_drivers = self.championship.max_drivers_per_team

        if max_drivers is None:
            return True, "No limit"

        if self.driver_count >= max_drivers:
            return False, f"Maximum {max_drivers} driver(s) reached"

        return True, "Can add driver"

    def clean(self):
        """Validate team has correct number of drivers before saving."""
        from django.core.exceptions import ValidationError

        is_valid, message = self.is_valid_driver_count

        # Only validate if team already exists (has drivers)
        if self.pk and not is_valid:
            raise ValidationError({
                'drivers': message
            })


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
        related_name='participants',
        help_text="Championship this participant is registered in"
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='participations'
    )

    # Team reference (optional - only for team championships)
    team = models.ForeignKey(
        'Team',
        on_delete=models.CASCADE,
        related_name='members',
        null=True,
        blank=True,
        help_text="Team this driver belongs to (only for team championships)"
    )

    car = models.ForeignKey(
        'cars.Car',
        on_delete=models.PROTECT,
        help_text="Car used by this driver/team"
    )

    racing_number = models.IntegerField(
        help_text="Driver or team racing number"
    )

    # Driver role (for team championships)
    role = models.CharField(
        max_length=100,
        blank=True,
        help_text="Driver role in team (e.g., 'Pro', 'Am', 'Silver', 'Gold'). Only for team championships."
    )

    # Metadata
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Participant'
        verbose_name_plural = 'Participants'
        unique_together = [
            ['championship', 'user'],
            ['championship', 'racing_number']
        ]
        ordering = ['racing_number']

    def __str__(self):
        if self.team:
            return f"#{self.racing_number} {self.user.username} ({self.team.name})"
        return f"#{self.racing_number} {self.user.username}"

    def clean(self):
        """Validate participant based on championship type."""
        from django.core.exceptions import ValidationError

        # Team championship: must have a team
        if self.championship.participant_type == ParticipantType.TEAM:
            if not self.team:
                raise ValidationError({
                    'team': 'Team is required for team championships.'
                })

            # Check if driver is already in another team in this championship
            existing_in_other_team = Driver.objects.filter(
                    championship=self.championship,
                    user=self.user,
                    team__isnull=False
                ).exclude(pk=self.pk)

            if existing_in_other_team.exists():
                other_team = existing_in_other_team.first().team
                raise ValidationError({
                    'driver': f'Driver is already in team "{other_team.name}" for this championship.'
                })

        # Individual championship: must NOT have a team
        if self.championship.participant_type == ParticipantType.INDIVIDUAL:
            if self.team:
                raise ValidationError({
                    'team': 'Individual championships cannot have teams.'
                })

    @property
    def is_team_member(self):
        return self.team is not None