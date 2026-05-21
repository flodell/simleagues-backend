from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from core.models.car import Car
from core.models.choices import (
    LeagueVisibility,
    LeagueMemberRole,
    RaceVisibility,
    RaceStatus,
    RaceEntryStatus,
    CarCategory,

)
from core.models.game import Game
from core.models.league import League, LeagueMembership
from core.models.race import Race, RaceEntry
from core.models.track import Track

User = get_user_model()


def auth_client(client, user):
    token = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")


class RaceCRUDTests(APITestCase):

    def setUp(self):
        self.creator = User.objects.create_user(username="creator", password="pass")
        self.staff = User.objects.create_user(username="staff", password="pass")
        self.member = User.objects.create_user(username="member", password="pass")
        self.other = User.objects.create_user(username="other", password="pass")

        self.game = Game.objects.create(name="Le Mans Ultimate", short_name="LMU")
        self.track = Track.objects.create(name="Circuit de la Sarthe", game=self.game, corners=14)
        self.league = League.objects.create(
            name="Test League", game=self.game, visibility=LeagueVisibility.PUBLIC
        )
        LeagueMembership.objects.create(league=self.league, user=self.creator, role=LeagueMemberRole.ADMIN)
        LeagueMembership.objects.create(league=self.league, user=self.staff, role=LeagueMemberRole.MODERATOR)
        LeagueMembership.objects.create(league=self.league, user=self.member, role=LeagueMemberRole.MEMBER)

        self.race = Race.objects.create(
            name="Test Race",
            league=self.league,
            creator=self.creator,
            track=self.track,
            scheduled_date="2025-06-01T14:00:00Z",
            visibility=RaceVisibility.PUBLIC,
            status=RaceStatus.SCHEDULED,
        )

        self.list_url = reverse("race-list")
        self.detail_url = reverse("race-detail", kwargs={"pk": self.race.pk})
        self.status_url = reverse("race-update-status", kwargs={"pk": self.race.pk})

    # --- List ---

    def test_list_unauthenticated_sees_public_only(self):
        Race.objects.create(
            name="Private Race",
            league=self.league,
            creator=self.creator,
            track=self.track,
            scheduled_date="2025-07-01T14:00:00Z",
            visibility=RaceVisibility.PRIVATE,
            status=RaceStatus.SCHEDULED,
        )
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [r["name"] for r in response.data["results"]]
        self.assertIn("Test Race", names)
        self.assertNotIn("Private Race", names)

    # --- Create ---

    def test_create_race_authenticated(self):
        auth_client(self.client, self.member)
        response = self.client.post(self.list_url, {
            "name": "New Race",
            "league": self.league.pk,
            "track": self.track.pk,
            "scheduled_date": "2025-08-01T14:00:00Z",
            "visibility": RaceVisibility.PUBLIC,
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Race.objects.get(pk=response.data["id"]).creator, self.member)

    def test_create_race_unauthenticated_blocked(self):
        response = self.client.post(self.list_url, {
            "name": "New Race",
            "track": self.track.pk,
            "scheduled_date": "2025-08-01T14:00:00Z",
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- Update ---

    def test_update_as_creator(self):
        auth_client(self.client, self.creator)
        response = self.client.patch(self.detail_url, {"name": "Updated Race"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_as_staff(self):
        auth_client(self.client, self.staff)
        response = self.client.patch(self.detail_url, {"name": "Updated Race"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_as_non_authorized_blocked(self):
        auth_client(self.client, self.other)
        response = self.client.patch(self.detail_url, {"name": "Updated Race"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # --- Delete ---

    def test_soft_delete_as_creator(self):
        auth_client(self.client, self.creator)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.race.refresh_from_db()
        self.assertFalse(self.race.is_active)

    def test_hard_delete_as_creator(self):
        auth_client(self.client, self.creator)
        response = self.client.delete(f"{self.detail_url}?hard=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Race.objects.filter(pk=self.race.pk).exists())

    def test_delete_as_non_authorized_blocked(self):
        auth_client(self.client, self.other)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # --- Update status ---

    def test_update_status_as_creator(self):
        auth_client(self.client, self.creator)
        response = self.client.post(self.status_url, {"status": RaceStatus.IN_PROGRESS}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.race.refresh_from_db()
        self.assertEqual(self.race.status, RaceStatus.IN_PROGRESS)

    def test_update_status_invalid(self):
        auth_client(self.client, self.creator)
        response = self.client.post(self.status_url, {"status": "INVALID"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_status_as_non_authorized_blocked(self):
        auth_client(self.client, self.other)
        response = self.client.post(self.status_url, {"status": RaceStatus.IN_PROGRESS}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class RaceEntryTests(APITestCase):

    def setUp(self):
        self.creator = User.objects.create_user(username="creator", password="pass")
        self.staff = User.objects.create_user(username="staff", password="pass")
        self.member = User.objects.create_user(username="member", password="pass")
        self.other = User.objects.create_user(username="other", password="pass")

        self.game = Game.objects.create(name="Le Mans Ultimate", short_name="LMU")
        self.track = Track.objects.create(name="Circuit de la Sarthe", game=self.game, corners=14)
        self.car = Car.objects.create(
            name="Ferrari 499P", game=self.game, category=CarCategory.HYPERCAR, year=2024
        )
        self.league = League.objects.create(
            name="Test League", game=self.game, visibility=LeagueVisibility.PUBLIC
        )
        LeagueMembership.objects.create(league=self.league, user=self.creator, role=LeagueMemberRole.ADMIN)
        LeagueMembership.objects.create(league=self.league, user=self.staff, role=LeagueMemberRole.MODERATOR)
        LeagueMembership.objects.create(league=self.league, user=self.member, role=LeagueMemberRole.MEMBER)

        self.race = Race.objects.create(
            name="Test Race",
            league=self.league,
            creator=self.creator,
            track=self.track,
            scheduled_date="2025-06-01T14:00:00Z",
            visibility=RaceVisibility.PUBLIC,
            status=RaceStatus.SCHEDULED,
        )

        self.register_url = reverse("race-entries-register", kwargs={"race_pk": self.race.pk})
        self.list_url = reverse("race-entries-list", kwargs={"race_pk": self.race.pk})

    def _entry_detail_url(self, entry_pk):
        return reverse("race-entries-detail", kwargs={"race_pk": self.race.pk, "pk": entry_pk})

    def _approve_url(self, entry_pk):
        return reverse("race-entries-approve", kwargs={"race_pk": self.race.pk, "pk": entry_pk})

    def _reject_url(self, entry_pk):
        return reverse("race-entries-reject", kwargs={"race_pk": self.race.pk, "pk": entry_pk})

    def _create_entry(self, user=None, racing_number=42, entry_status=RaceEntryStatus.PENDING):
        return RaceEntry.objects.create(
            race=self.race,
            user=user,
            car=self.car,
            racing_number=racing_number,
            status=entry_status,
        )

    # --- Register ---

    def test_register_public_league_auto_approved(self):
        auth_client(self.client, self.member)
        response = self.client.post(self.register_url, {
            "car": self.car.pk,
            "racing_number": 42,
            "user": self.member.pk,
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        entry = RaceEntry.objects.get(race=self.race, user=self.member)
        self.assertEqual(entry.status, RaceEntryStatus.APPROVED)

    def test_register_invite_only_pending(self):
        self.league.visibility = LeagueVisibility.INVITE_ONLY
        self.league.save()
        auth_client(self.client, self.member)
        response = self.client.post(self.register_url, {
            "car": self.car.pk,
            "racing_number": 42,
            "user": self.member.pk,
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        entry = RaceEntry.objects.get(race=self.race, user=self.member)
        self.assertEqual(entry.status, RaceEntryStatus.PENDING)

    def test_register_private_league_blocked(self):
        self.league.visibility = LeagueVisibility.PRIVATE
        self.league.save()
        auth_client(self.client, self.member)
        response = self.client.post(self.register_url, {
            "car": self.car.pk,
            "racing_number": 42,
            "user": self.member.pk,
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_register_non_member_blocked(self):
        auth_client(self.client, self.other)
        response = self.client.post(self.register_url, {
            "car": self.car.pk,
            "racing_number": 42,
            "user": self.other.pk,
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_register_non_scheduled_race_blocked(self):
        self.race.status = RaceStatus.COMPLETED
        self.race.save()
        auth_client(self.client, self.member)
        response = self.client.post(self.register_url, {
            "car": self.car.pk,
            "racing_number": 42,
            "user": self.member.pk,
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- Approve/Reject ---

    def test_staff_approve_entry(self):
        entry = self._create_entry(user=self.member)
        auth_client(self.client, self.staff)
        response = self.client.post(self._approve_url(entry.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        entry.refresh_from_db()
        self.assertEqual(entry.status, RaceEntryStatus.APPROVED)

    def test_non_staff_approve_blocked(self):
        entry = self._create_entry(user=self.member)
        auth_client(self.client, self.member)
        response = self.client.post(self._approve_url(entry.pk))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_staff_reject_entry(self):
        entry = self._create_entry(user=self.member, racing_number=43)
        auth_client(self.client, self.staff)
        response = self.client.post(self._reject_url(entry.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        entry.refresh_from_db()
        self.assertEqual(entry.status, RaceEntryStatus.REJECTED)

    # --- Destroy ---

    def test_entrant_can_delete_own_entry(self):
        entry = self._create_entry(user=self.member, racing_number=44)
        auth_client(self.client, self.member)
        response = self.client.delete(self._entry_detail_url(entry.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(RaceEntry.objects.filter(pk=entry.pk).exists())

    def test_other_cannot_delete_entry(self):
        entry = self._create_entry(user=self.member, racing_number=45)
        auth_client(self.client, self.other)
        response = self.client.delete(self._entry_detail_url(entry.pk))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)