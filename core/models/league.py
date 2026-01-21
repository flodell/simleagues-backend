import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models

from core.models.choices import LeagueVisibility, LeagueMemberRole, JoinRequestStatus
from core.models.game import Game
from django.utils import timezone

# Create your models here.

User = get_user_model()


class League(models.Model):
    """
    Represents a racing league organization.

    A league is a group of drivers who compete together.
    Leagues can have multiple championship over time.
    """

    # Basic Information
    name = models.CharField(
        max_length=200, help_text="League name (e.g., 'Friday Night Endurance League')"
    )

    description = models.TextField(blank=True, help_text="League description and rules")

    # Creator
    creator = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="created_leagues",
        help_text="User who created this league",
    )

    # Visibility and Access Control
    visibility = models.CharField(
        max_length=20,
        choices=LeagueVisibility.choices,
        default=LeagueVisibility.PUBLIC,
        help_text="League visibility and join requirements",
    )

    invitation_code = models.CharField(
        max_length=32,
        unique=True,
        blank=True,
        help_text="Unique invitation code for INVITE_ONLY leagues",
    )

    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='LeagueMembership',
        related_name='leagues'
    )

    game = models.ForeignKey(
        Game,
        on_delete=models.PROTECT,
        related_name='leagues'
    )
    is_active = models.BooleanField(default=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "League"
        verbose_name_plural = "Leagues"

    def __str__(self):
        return self.name

    @staticmethod
    def generate_invitation_code():
        """Generate a unique invitation code."""
        return secrets.token_urlsafe(16)  # Génère un code de 22 caractères

    def regenerate_invitation_code(self):
        """Regenerate the invitation code (useful to revoke access)."""
        self.invitation_code = self.generate_invitation_code()
        self.save()
        return self.invitation_code

    def save(self, *args, **kwargs):
        """Generate invitation code if INVITE_ONLY and not set."""
        if self.visibility == LeagueVisibility.INVITE_ONLY and not self.invitation_code:
            self.invitation_code = self.generate_invitation_code()
        super().save(*args, **kwargs)

    @property
    def member_count(self):
        """Get total number of members."""
        return self.memberships.count()

    def get_active_championships(self):
        """Get all active championship."""
        return self.championships.filter(status="ACTIVE")

    # Permission checks
    def is_admin(self, user):
        """Check if user is an admin of this league."""
        return self.memberships.filter(user=user, role=LeagueMemberRole.ADMIN).exists()

    def is_member(self, user):
        """Check if user is a member (admin or regular)."""
        return self.memberships.filter(user=user).exists()

    def is_moderator(self, user):
        """Check if user is a moderator of this league."""
        return self.memberships.filter(
            user=user, role=LeagueMemberRole.MODERATOR
        ).exists()

    def is_staff(self, user):
        """Check if user is admin or moderator (has staff permissions)."""
        return self.memberships.filter(
            user=user, role__in=[LeagueMemberRole.ADMIN, LeagueMemberRole.MODERATOR]
        ).exists()

    # Specific permission checks
    def can_manage_races(self, user):
        """Check if user can create and manage races."""
        return self.is_staff(user)

    def can_manage_championships(self, user):
        """Check if user can create and manage championship."""
        return self.is_staff(user)

    def can_approve_members(self, user):
        """Check if user can approve join requests."""
        return self.is_staff(user)

    def can_kick_members(self, user):
        """Check if user can kick members."""
        return self.is_staff(user)

    def can_edit_league(self, user):
        """Check if user can edit league settings."""
        return self.is_admin(user)

    def can_delete_league(self, user):
        """Check if user can delete the league."""
        return self.is_admin(user)

    def can_promote_to_moderator(self, user):
        """Check if user can promote members to moderator."""
        return self.is_admin(user)

    def can_promote_to_admin(self, user):
        """Check if user can promote members to admin."""
        return self.is_admin(user)

    def can_user_join(self, user):
        """
        Check if a user can join the league.

        Returns tuple: (can_join: bool, reason: str)
        """
        if self.is_member(user):
            return False, "Already a member"
        match self.visibility:
            case LeagueVisibility.PUBLIC:
                return True, "Public league"
            case LeagueVisibility.INVITE_ONLY:
                return False, "Invitation code required"
            case LeagueVisibility.PRIVATE:
                return False, "Admin approval required"

        return False, "Unknown visibility setting"


class LeagueMembership(models.Model):
    """
    Represents a user's membership in a league.

    Tracks the role and join date.
    """

    league = models.ForeignKey(
        League, on_delete=models.CASCADE, related_name="memberships"
    )

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="league_memberships"
    )

    role = models.CharField(
        max_length=10,
        choices=LeagueMemberRole.choices,
        default=LeagueMemberRole.MEMBER,
        help_text="Member role in the league",
    )

    # Metadata
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "League Membership"
        verbose_name_plural = "League Memberships"
        unique_together = ["league", "user"]
        ordering = ["-joined_at"]

    def __str__(self):
        return f"{self.user.username} - {self.league.name} ({self.role})"


class LeagueJoinRequest(models.Model):
    """
    Represents a user's request to join a private league.

    Used when league visibility is PRIVATE and user needs admin approval.
    """

    league = models.ForeignKey(
        League, on_delete=models.CASCADE, related_name="join_requests"
    )

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="league_join_requests"
    )

    status = models.CharField(
        max_length=10,
        choices=JoinRequestStatus.choices,
        default=JoinRequestStatus.PENDING,
        help_text="Status of the join request",
    )

    message = models.TextField(blank=True, help_text="Optional message from the user")

    # Admin response
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_join_requests",
        help_text="Admin who reviewed the request",
    )

    admin_message = models.TextField(
        blank=True, help_text="Optional message from admin"
    )

    # Metadata
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "League Join Request"
        verbose_name_plural = "League Join Requests"
        unique_together = ["league", "user", "status"]
        ordering = ["-requested_at"]

    def __str__(self):
        return f"{self.user.username} → {self.league.name} ({self.status})"

    def approve(self, admin_user, message=""):
        """Approve the join request and create membership."""
        self.status = JoinRequestStatus.APPROVED
        self.reviewed_by = admin_user
        self.admin_message = message
        self.reviewed_at = timezone.now()
        self.save()

        # Create membership
        LeagueMembership.objects.create(
            league=self.league, user=self.user, role=LeagueMemberRole.MEMBER
        )

    def reject(self, admin_user, message=""):
        """Reject the join request."""
        self.status = JoinRequestStatus.REJECTED
        self.reviewed_by = admin_user
        self.admin_message = message
        self.reviewed_at = timezone.now()
        self.save()
