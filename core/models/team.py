from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models, transaction

from core.models import League
from core.models.choices import (
    TeamRole,
    TeamJoinRequestStatus,
    LeagueTeamRegistrationStatus,
)

User = get_user_model()


class Team(models.Model):
    """
    Independent racing team that can participate in multiple leagues and events.

    Teams exist globally and are not tied to a specific league or championship.
    They can register in multiple leagues and participate in various events.
    """

    # Team Information
    name = models.CharField(
        max_length=200,
        unique=True,
    )
    logo = models.ImageField(upload_to="team_logo/", null=True, blank=True)
    description = models.TextField(blank=True)

    total_races = models.PositiveIntegerField(default=0)
    total_wins = models.PositiveIntegerField(default=0)
    total_podiums = models.PositiveIntegerField(default=0)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Team"
        verbose_name_plural = "Teams"
        ordering = ("name",)

    def __str__(self):
        return self.name

    def clean(self):
        errors = {}

        if not self.name.strip():
            errors["name"] = "Team name can't be empty"
        if len(self.name) < 3:
            errors["name"] = "Team name can't be less than 3 characters"
        if errors:
            raise ValidationError(errors)

    @transaction.atomic
    def transfer_ownership(self, new_owner):
        try:
            new_owner_membership = self.memberships.get(user=new_owner, is_active=True)
        except TeamMembership.DoesNotExist:
            raise ValueError(f"{new_owner.username} is not a member of this team")

        old_owner_membership = self.memberships.get(role="owner", is_active=True)
        old_owner_membership.role = TeamRole.MANAGER
        old_owner_membership.save()

        # Nouveau owner
        new_owner_membership.role = TeamRole.OWNER
        new_owner_membership.save()

        return new_owner_membership


class TeamMembership(models.Model):
    """
    Represents a user's membership in a team with a specific role.

    Roles:
    - owner: Team creator, full control (only one per team)
    - manager: Can manage team, entries, and lineups
    - driver: Active racing driver
    - reserve: Reserve/backup driver
    """

    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="memberships",
        help_text="Team this membership belongs to",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="team_memberships",
        help_text="User who is a member of this team",
    )
    role = models.CharField(max_length=20, choices=TeamRole)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "TeamMembership"
        verbose_name_plural = "TeamMemberships"
        unique_together = ("team", "user")
        ordering = (
            "team",
            "created_at",
        )

    def clean(self):
        errors = {}

        if self.role == TeamRole.OWNER:
            existing_owner = (
                TeamMembership.objects.filter(team=self.team, role=TeamRole.OWNER)
                .exclude(pk=self.pk)
                .exists()
            )
            if existing_owner:
                f"Team already has an owner: {existing_owner.user.username}."
        if errors:
            raise ValidationError(errors)


class TeamJoinRequest(models.Model):
    """
    Represents a user's request to join a team.

    Users can request to join teams, and team owners/managers can approve or reject.
    """

    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="join_requests",
        help_text="Team join request",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="team_join_requests",
        help_text="User join request",
    )
    message = models.TextField(
        blank=True,
        help_text="Optional message from the user explaining why they want to join",
    )

    status = models.CharField(
        max_length=20,
        choices=TeamJoinRequestStatus.choices,
        default=TeamJoinRequestStatus.PENDING,
    )

    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_team_requests",
        help_text="Owner/manager who accepted or rejected the request",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "TeamJoinRequest"
        verbose_name_plural = "TeamJoinRequests"
        ordering = (
            "team",
            "created_at",
        )
        constraints = [
            models.UniqueConstraint(
                fields=["team", "user"],
                condition=models.Q(status=TeamJoinRequestStatus.PENDING),
                name="unique_team_join_request_pending",
            )
        ]

    def __str__(self):
        return f"{self.user.username} → {self.team.name} ({self.get_status_display()})"

    def clean(self):
        errors = {}

        if TeamMembership.objects.filter(team=self.team, user=self.user).exists():
            errors["user"] = (
                f"{self.user.username} is already a member of {self.team.name}."
            )
        if self.status == "pending":
            existing = TeamJoinRequest.objects.filter(
                team=self.team,
                user=self.user,
                status=TeamJoinRequestStatus.PENDING,
            ).exclude(pk=self.pk)

            if existing.exists():
                errors["user"] = "You already have a pending request to join this team."
        if errors:
            raise ValidationError(errors)

    def accept(self, resolved_by, role=TeamRole.DRIVER):
        """
        Accept the join request and create a team membership.

        Args:
            resolved_by: User who is accepting the request (owner/manager)
            role: Role to assign to the new member (default: 'driver')

        Returns:
            TeamMembership: The created membership
        """

        if self.status != TeamJoinRequestStatus.PENDING:
            raise ValidationError("Can only accept pending requests")

        membership = TeamMembership.objects.create(
            team=self.team,
            user=self.user,
            role=role,
        )
        self.status = TeamJoinRequestStatus.APPROVED
        self.resolved_by = resolved_by
        self.save()

        return membership

    def reject(self, resolved_by):
        """
        Reject the join request.

        Args:
            resolved_by: User who is rejecting the request (owner/manager)
        """
        if self.status != TeamJoinRequestStatus.PENDING:
            raise ValidationError("Can only reject pending requests")
        self.status = TeamJoinRequestStatus.REJECTED
        self.resolved_by = resolved_by
        self.save()
        pass


class LeagueTeamRegistration(models.Model):

    league = models.ForeignKey(
        League,
        on_delete=models.CASCADE,
        related_name="team_registrations",
        help_text="League team registration",
    )

    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="league_registrations",
        help_text="Team registration",
    )

    status = models.CharField(
        max_length=20,
        choices=LeagueTeamRegistrationStatus.choices,
        default=LeagueTeamRegistrationStatus.PENDING,
        help_text="Team registration status",
    )
    resolved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_team_registrations",
    )

    ban_reason = models.TextField(
        blank=True, help_text="Banned reason (if status is banned"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "LeagueTeamRegistration"
        verbose_name_plural = "LeagueTeamRegistrations"
        unique_together = (("league", "team"),)
        ordering = ("created_at",)

    def __str__(self):
        return f"{self.team.name} → {self.league.name} ({self.get_status_display()})"

    def clean(self):
        errors = {}
        # Cannot register if league is not active
        if hasattr(self, "league") and not self.league.is_active:
            errors["league"] = (
                f"League {self.league.name} is not accepting registration"
            )

        if errors:
            raise ValidationError(errors)

    def accept(self, resolved_by):
        if self.status == LeagueTeamRegistrationStatus.BANNED:
            raise ValidationError("Cannot approved a banned registrations")
        self.status = LeagueTeamRegistrationStatus.APPROVED
        self.resolved_by = resolved_by
        self.save()

    def reject(self, resolved_by):
        if self.status == LeagueTeamRegistrationStatus.BANNED:
            raise ValidationError("Cannot reject a banned registrations")
        self.status = LeagueTeamRegistrationStatus.REJECTED
        self.resolved_by = resolved_by
        self.save()

    def ban(self, reason=""):
        self.status = LeagueTeamRegistrationStatus.BANNED
        self.ban_reason = reason
        self.save()
