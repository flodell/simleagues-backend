from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from core.models.car import Car
from core.models.championship import Championship, ChampionshipEntry
from core.models.choices import (
    LeagueVisibility,
    LeagueMemberRole,
    ChampionshipStatus,
    ChampionshipEntryStatus,
    ParticipantType,
    CarCategory,
    TeamRole,
)
from core.models.game import Game
from core.models.league import League, LeagueMembership
from core.models.team import Team, TeamMembership

User = get_user_model()


def auth_client(client, user):
    token = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")


class ChampionshipCRUDTests(APITestCase):

    def setUp(self):
        self.admin = User.objects.create_user(username="admin", password="pass")
        self.moderator = User.objects.create_user(username="moderator", password="pass")
        self.member = User.objects.create_user(username="member", password="pass")
        self.other = User.objects.create_user(username="other", password="pass")

        self.game = Game.objects.create(name="Le Mans Ultimate", short_name="LMU")
        self.league = League.objects.create(
            name="Test League", game=self.game, visibility=LeagueVisibility.PUBLIC
        )
        LeagueMembership.objects.create(
            league=self.league, user=self.admin, role=LeagueMemberRole.ADMIN
        )
        LeagueMembership.objects.create(
            league=self.league, user=self.moderator, role=LeagueMemberRole.MODERATOR
        )
        LeagueMembership.objects.create(
            league=self.league, user=self.member, role=LeagueMemberRole.MEMBER
        )

        self.championship = Championship.objects.create(
            league=self.league,
            name="2025 Season",
            start_date="2025-01-01",
            participant_type=ParticipantType.INDIVIDUAL,
            status=ChampionshipStatus.UPCOMING,
        )

        self.list_url = reverse("championship-list")
        self.detail_url = reverse(
            "championship-detail", kwargs={"pk": self.championship.pk}
        )
        self.status_url = reverse(
            "championship-update-status", kwargs={"pk": self.championship.pk}
        )

    # --- List ---

    def test_list_unauthenticated(self):
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_filter_by_participant_type(self):
        Championship.objects.create(
            league=self.league,
            name="Team Champ",
            start_date="2025-01-01",
            participant_type=ParticipantType.TEAM,
            status=ChampionshipStatus.UPCOMING,
        )
        response = self.client.get(
            self.list_url, {"participant_type": ParticipantType.TEAM}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["name"], "Team Champ")

    # --- Create ---

    def test_create_as_admin(self):
        auth_client(self.client, self.admin)
        response = self.client.post(
            self.list_url,
            {
                "name": "New Championship",
                "league": self.league.pk,
                "participant_type": ParticipantType.INDIVIDUAL,
                "start_date": "2026-01-01",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_as_member_blocked(self):
        auth_client(self.client, self.member)
        response = self.client.post(
            self.list_url,
            {
                "name": "New Championship",
                "league": self.league.pk,
                "participant_type": ParticipantType.INDIVIDUAL,
                "start_date": "2026-01-01",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_name_too_short(self):
        auth_client(self.client, self.admin)
        response = self.client.post(
            self.list_url,
            {
                "name": "AB",
                "league": self.league.pk,
                "participant_type": ParticipantType.INDIVIDUAL,
                "start_date": "2026-01-01",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_end_date_before_start_date(self):
        auth_client(self.client, self.admin)
        response = self.client.post(
            self.list_url,
            {
                "name": "Valid Name",
                "league": self.league.pk,
                "participant_type": ParticipantType.INDIVIDUAL,
                "start_date": "2026-01-01",
                "end_date": "2025-01-01",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- Update status ---

    def test_update_status_as_admin(self):
        auth_client(self.client, self.admin)
        response = self.client.post(
            self.status_url, {"status": "ACTIVE"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.championship.refresh_from_db()
        self.assertEqual(self.championship.status, ChampionshipStatus.ACTIVE)

    def test_update_status_as_moderator_blocked(self):
        auth_client(self.client, self.moderator)
        response = self.client.post(
            self.status_url, {"status": "ACTIVE"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_status_invalid(self):
        auth_client(self.client, self.admin)
        response = self.client.post(
            self.status_url, {"status": "INVALID"}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ChampionshipEntryTests(APITestCase):

    def setUp(self):
        self.admin = User.objects.create_user(username="admin", password="pass")
        self.member = User.objects.create_user(username="member", password="pass")
        self.other = User.objects.create_user(username="other", password="pass")

        self.game = Game.objects.create(name="Le Mans Ultimate", short_name="LMU")
        self.car = Car.objects.create(
            name="Ferrari 499P",
            game=self.game,
            category=CarCategory.HYPERCAR,
            year=2024,
        )

        self.league = League.objects.create(
            name="Test League", game=self.game, visibility=LeagueVisibility.PUBLIC
        )
        LeagueMembership.objects.create(
            league=self.league, user=self.admin, role=LeagueMemberRole.ADMIN
        )
        LeagueMembership.objects.create(
            league=self.league, user=self.member, role=LeagueMemberRole.MEMBER
        )

        self.championship = Championship.objects.create(
            league=self.league,
            name="2025 Season",
            start_date="2025-01-01",
            participant_type=ParticipantType.INDIVIDUAL,
            status=ChampionshipStatus.UPCOMING,
            max_participants=10,
        )

        self.list_url = reverse(
            "championship-entries-list",
            kwargs={"championship_pk": self.championship.pk},
        )
        self.register_url = reverse(
            "championship-entries-register",
            kwargs={"championship_pk": self.championship.pk},
        )

    def _entry_detail_url(self, entry_pk):
        return reverse(
            "championship-entries-detail",
            kwargs={
                "championship_pk": self.championship.pk,
                "pk": entry_pk,
            },
        )

    def _approve_url(self, entry_pk):
        return reverse(
            "championship-entries-approve",
            kwargs={
                "championship_pk": self.championship.pk,
                "pk": entry_pk,
            },
        )

    def _reject_url(self, entry_pk):
        return reverse(
            "championship-entries-reject",
            kwargs={
                "championship_pk": self.championship.pk,
                "pk": entry_pk,
            },
        )

    def _create_entry(
        self,
        user=None,
        team=None,
        racing_number=42,
        status=ChampionshipEntryStatus.PENDING,
        championship=None,
    ):
        return ChampionshipEntry.objects.create(
            championship=championship or self.championship,
            user=user,
            team=team,
            car=self.car,
            racing_number=racing_number,
            status=status,
        )

    # --- Register ---

    def test_register_public_league_auto_approved(self):
        auth_client(self.client, self.member)
        response = self.client.post(
            self.register_url,
            {
                "car": self.car.pk,
                "racing_number": 42,
                "user": self.member.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        entry = ChampionshipEntry.objects.get(
            championship=self.championship, user=self.member
        )
        self.assertEqual(entry.status, ChampionshipEntryStatus.APPROVED)

    def test_register_invite_only_pending(self):
        self.league.visibility = LeagueVisibility.INVITE_ONLY
        self.league.save()
        auth_client(self.client, self.member)
        response = self.client.post(
            self.register_url,
            {
                "car": self.car.pk,
                "racing_number": 42,
                "user": self.member.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        entry = ChampionshipEntry.objects.get(
            championship=self.championship, user=self.member
        )
        self.assertEqual(entry.status, ChampionshipEntryStatus.PENDING)

    def test_register_private_league_blocked(self):
        self.league.visibility = LeagueVisibility.PRIVATE
        self.league.save()
        auth_client(self.client, self.member)
        response = self.client.post(
            self.register_url,
            {
                "car": self.car.pk,
                "racing_number": 42,
                "user": self.member.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_register_non_member_blocked(self):
        auth_client(self.client, self.other)
        response = self.client.post(
            self.register_url,
            {
                "car": self.car.pk,
                "racing_number": 42,
                "user": self.other.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_register_completed_championship_blocked(self):
        self.championship.status = ChampionshipStatus.COMPLETED
        self.championship.save()
        auth_client(self.client, self.member)
        response = self.client.post(
            self.register_url,
            {
                "car": self.car.pk,
                "racing_number": 42,
                "user": self.member.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_team_entry_as_non_manager_blocked(self):
        team_champ = Championship.objects.create(
            league=self.league,
            name="Team Champ",
            start_date="2025-01-01",
            participant_type=ParticipantType.TEAM,
            status=ChampionshipStatus.UPCOMING,
        )
        team = Team.objects.create(name="Red Racing")
        TeamMembership.objects.create(team=team, user=self.member, role=TeamRole.DRIVER)
        register_url = reverse(
            "championship-entries-register", kwargs={"championship_pk": team_champ.pk}
        )
        auth_client(self.client, self.member)
        response = self.client.post(
            register_url,
            {
                "car": self.car.pk,
                "racing_number": 42,
                "team": team.pk,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # --- Staff actions ---

    def test_staff_approve_entry(self):
        entry = self._create_entry(user=self.member)
        auth_client(self.client, self.admin)
        response = self.client.post(self._approve_url(entry.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        entry.refresh_from_db()
        self.assertEqual(entry.status, ChampionshipEntryStatus.APPROVED)

    def test_non_staff_approve_blocked(self):
        entry = self._create_entry(user=self.member)
        auth_client(self.client, self.member)
        response = self.client.post(self._approve_url(entry.pk))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_reject_entry(self):
        entry = self._create_entry(user=self.member, racing_number=43)
        auth_client(self.client, self.admin)
        response = self.client.post(self._reject_url(entry.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        entry.refresh_from_db()
        self.assertEqual(entry.status, ChampionshipEntryStatus.REJECTED)

    def test_entrant_can_delete_own_entry(self):
        entry = self._create_entry(user=self.member, racing_number=44)
        auth_client(self.client, self.member)
        response = self.client.delete(self._entry_detail_url(entry.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(ChampionshipEntry.objects.filter(pk=entry.pk).exists())

    def test_other_cannot_delete_entry(self):
        entry = self._create_entry(user=self.member, racing_number=45)
        auth_client(self.client, self.other)
        response = self.client.delete(self._entry_detail_url(entry.pk))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
