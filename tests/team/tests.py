"""
Tests for Team models - Pragmatic version.
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from core.models import Game
from core.models.team import (
    Team,
    TeamMembership,
    TeamJoinRequest,
    LeagueTeamRegistration,
)
from core.models.league import League
from core.models.choices import LeagueVisibility, TeamRole, TeamJoinRequestStatus, LeagueTeamRegistrationStatus

User = get_user_model()


class TeamModelTests(TestCase):
    """Tests for Team model."""

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='pass')

    def test_create_team(self):
        """Test basic team creation."""
        team = Team.objects.create(
            name='Velocity Racing',
            owner=self.user,
            description='A racing team'
        )

        self.assertEqual(team.name, 'Velocity Racing')
        self.assertEqual(team.owner, self.user)

    def test_team_name_unique(self):
        """Test team names must be unique."""
        Team.objects.create(name='Velocity Racing', owner=self.user)

        with self.assertRaises(Exception):
            Team.objects.create(name='Velocity Racing', owner=self.user)


class TeamMembershipModelTests(TestCase):
    """Tests for TeamMembership model."""

    def setUp(self):
        self.owner = User.objects.create_user(username='owner', password='pass')
        self.team = Team.objects.create(name='Test Team', owner=self.owner)

    def test_create_membership(self):
        """Test creating a membership."""
        user = User.objects.create_user(username='driver', password='pass')
        membership = TeamMembership.objects.create(
            team=self.team,
            user=user,
            role=TeamRole.DRIVER
        )

        self.assertEqual(membership.team, self.team)
        self.assertEqual(membership.user, user)
        self.assertEqual(membership.role, TeamRole.DRIVER)

    def test_only_one_owner_per_team(self):
        """Test team can only have one owner."""
        user1 = User.objects.create_user(username='user1', password='pass')
        user2 = User.objects.create_user(username='user2', password='pass')

        TeamMembership.objects.create(team=self.team, user=user1, role='owner')

        membership2 = TeamMembership(team=self.team, user=user2, role='owner')
        with self.assertRaises(ValidationError):
            membership2.full_clean()


class TeamJoinRequestModelTests(TestCase):
    """Tests for TeamJoinRequest model."""

    def setUp(self):
        self.owner = User.objects.create_user(username='owner', password='pass')
        self.team = Team.objects.create(name='Test Team', owner=self.owner)
        self.user = User.objects.create_user(username='applicant', password='pass')

    def test_create_and_accept_request(self):
        """Test creating and accepting a join request."""
        request = TeamJoinRequest.objects.create(
            team=self.team,
            user=self.user,
            message='I want to join!'
        )

        self.assertEqual(request.status, TeamJoinRequestStatus.PENDING)

        # Accept request
        membership = request.accept(resolved_by=self.owner, role=TeamRole.DRIVER)

        self.assertEqual(membership.user, self.user)
        self.assertEqual(membership.role, TeamRole.DRIVER)
        self.assertEqual(request.status, TeamJoinRequestStatus.APPROVED)

    def test_cannot_request_if_already_member(self):
        """Test existing members cannot request to join."""
        TeamMembership.objects.create(team=self.team, user=self.user, role='driver')

        request = TeamJoinRequest(team=self.team, user=self.user)
        with self.assertRaises(ValidationError):
            request.full_clean()


class LeagueTeamRegistrationModelTests(TestCase):
    """Tests for LeagueTeamRegistration model."""

    def setUp(self):
        self.owner = User.objects.create_user(username='owner', password='pass')
        self.team = Team.objects.create(name='Test Team', owner=self.owner)
        self.league_owner = User.objects.create_user(username='league_owner', password='pass')
        self.game = Game.objects.create(name="Le mans ultimate", short_name="LMU")
        self.league = League.objects.create(
            name='Test League',
            creator=self.league_owner,
            visibility=LeagueVisibility.PUBLIC,
            game=self.game,
        )


    def test_create_and_approve_registration(self):
        """Test creating and approving a registration."""
        registration = LeagueTeamRegistration.objects.create(
            league=self.league,
            team=self.team
        )

        self.assertEqual(registration.status, LeagueTeamRegistrationStatus.PENDING)

        # Approve
        admin = User.objects.create_user(username='admin', password='pass')
        registration.accept(resolved_by=admin)

        self.assertEqual(registration.status, LeagueTeamRegistrationStatus.APPROVED)
        self.assertEqual(registration.resolved_by, admin)

    def test_ban_registration(self):
        """Test banning a team from a league."""
        registration = LeagueTeamRegistration.objects.create(
            league=self.league,
            team=self.team
        )

        registration.ban(reason='Toxic behavior')

        self.assertEqual(registration.status, LeagueTeamRegistrationStatus.BANNED)
        self.assertEqual(registration.ban_reason, 'Toxic behavior')