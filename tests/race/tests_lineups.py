from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from core.models.car import Car
from core.models.choices import (
    LeagueMemberRole,
    LeagueVisibility,
    RaceEntryStatus,
    RaceVisibility,
    TeamRole,
)
from core.models.game import Game
from core.models.league import League, LeagueMembership
from core.models.races.entry import RaceEntry
from core.models.races.lineup import RaceLineup, RaceLineupDriver
from core.models.races.race import Race
from core.models.team import Team, TeamMembership
from core.models.track import Track

User = get_user_model()


def auth_client(client, user):
    token = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")


class RaceLineupViewSetTests(APITestCase):

    def setUp(self):
        # Users
        self.race_creator = User.objects.create_user(username="race_creator", password="pass")
        self.league_admin = User.objects.create_user(username="league_admin", password="pass")
        self.team_owner = User.objects.create_user(username="team_owner", password="pass")
        self.team_driver = User.objects.create_user(username="team_driver", password="pass")
        self.outsider = User.objects.create_user(username="outsider", password="pass")

        # Game / Track / League
        self.game = Game.objects.create(name="Le Mans Ultimate")
        self.track = Track.objects.create(
            game=self.game, name="Spa-Francorchamps", corners=20
        )
        self.car = Car.objects.create(game=self.game, name="Ferrari 296 GT3", year=2020)

        self.league = League.objects.create(
            name="Test League",
            visibility=LeagueVisibility.PUBLIC,
            game=self.game,
        )
        LeagueMembership.objects.create(
            league=self.league, user=self.league_admin, role=LeagueMemberRole.ADMIN
        )

        # Race
        self.race = Race.objects.create(
            name="Test Race",
            league=self.league,
            track=self.track,
            scheduled_date=timezone.now() + timedelta(days=7),
            visibility=RaceVisibility.PUBLIC,
            creator=self.race_creator,
        )

        # Team with owner + driver
        self.team = Team.objects.create(name="Red Racing")
        TeamMembership.objects.create(
            team=self.team, user=self.team_owner, role=TeamRole.OWNER
        )
        TeamMembership.objects.create(
            team=self.team, user=self.team_driver, role=TeamRole.DRIVER
        )

        # Team RaceEntry (approved)
        self.race_entry = RaceEntry.objects.create(
            race=self.race,
            team=self.team,
            car=self.car,
            racing_number=42,
            status=RaceEntryStatus.APPROVED,
        )

        self.list_url = reverse("race-lineups-list", kwargs={"race_pk": self.race.pk})

    def detail_url(self, lineup_pk):
        return reverse(
            "race-lineups-detail", kwargs={"race_pk": self.race.pk, "pk": lineup_pk}
        )

    def add_driver_url(self, lineup_pk):
        return reverse(
            "race-lineups-add-driver",
            kwargs={"race_pk": self.race.pk, "pk": lineup_pk},
        )

    def remove_driver_url(self, lineup_pk):
        return reverse(
            "race-lineups-remove-driver",
            kwargs={"race_pk": self.race.pk, "pk": lineup_pk},
        )

    # --- CRUD ---

    def test_create_lineup_as_staff(self):
        auth_client(self.client, self.league_admin)
        response = self.client.post(
            self.list_url, {"race_entry": self.race_entry.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            RaceLineup.objects.filter(race=self.race, race_entry=self.race_entry).exists()
        )

    def test_create_lineup_with_race_entry_from_another_race(self):
        # Create a 2nd race and a RaceEntry attached to it
        other_race = Race.objects.create(
            name="Other Race",
            league=self.league,
            track=self.track,
            scheduled_date=timezone.now() + timedelta(days=14),
            visibility=RaceVisibility.PUBLIC,
            creator=self.race_creator,
        )
        other_entry = RaceEntry.objects.create(
            race=other_race,
            team=self.team,
            car=self.car,
            racing_number=99,
            status=RaceEntryStatus.APPROVED,
        )

        auth_client(self.client, self.league_admin)
        response = self.client.post(
            self.list_url, {"race_entry": other_entry.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_lineup_duplicate_blocked(self):
        RaceLineup.objects.create(race=self.race, race_entry=self.race_entry)

        auth_client(self.client, self.league_admin)
        response = self.client.post(
            self.list_url, {"race_entry": self.race_entry.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- Permissions ---

    def test_create_lineup_as_team_owner(self):
        auth_client(self.client, self.team_owner)
        response = self.client.post(
            self.list_url, {"race_entry": self.race_entry.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_lineup_as_outsider_forbidden(self):
        auth_client(self.client, self.outsider)
        response = self.client.post(
            self.list_url, {"race_entry": self.race_entry.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_lineup_as_team_driver_forbidden(self):
        # team_driver is a member of the team but only DRIVER role, not OWNER/MANAGER
        auth_client(self.client, self.team_driver)
        response = self.client.post(
            self.list_url, {"race_entry": self.race_entry.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # --- Add / Remove driver ---

    def test_add_driver_to_lineup(self):
        lineup = RaceLineup.objects.create(race=self.race, race_entry=self.race_entry)

        auth_client(self.client, self.team_owner)
        response = self.client.post(
            self.add_driver_url(lineup.pk),
            {"user": self.team_driver.pk, "role": "Pro"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            RaceLineupDriver.objects.filter(lineup=lineup, user=self.team_driver).exists()
        )

    def test_add_driver_not_in_team_blocked(self):
        lineup = RaceLineup.objects.create(race=self.race, race_entry=self.race_entry)

        auth_client(self.client, self.team_owner)
        response = self.client.post(
            self.add_driver_url(lineup.pk),
            {"user": self.outsider.pk, "role": "Pro"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_remove_driver_from_lineup(self):
        lineup = RaceLineup.objects.create(race=self.race, race_entry=self.race_entry)
        RaceLineupDriver.objects.create(lineup=lineup, user=self.team_driver)

        auth_client(self.client, self.team_owner)
        response = self.client.post(
            self.remove_driver_url(lineup.pk),
            {"user_id": self.team_driver.pk},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(
            RaceLineupDriver.objects.filter(lineup=lineup, user=self.team_driver).exists()
        )

    # --- Destroy ---

    def test_destroy_lineup_as_team_owner(self):
        lineup = RaceLineup.objects.create(race=self.race, race_entry=self.race_entry)

        auth_client(self.client, self.team_owner)
        response = self.client.delete(self.detail_url(lineup.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(RaceLineup.objects.filter(pk=lineup.pk).exists())

    def test_destroy_lineup_as_outsider_forbidden(self):
        lineup = RaceLineup.objects.create(race=self.race, race_entry=self.race_entry)

        auth_client(self.client, self.outsider)
        response = self.client.delete(self.detail_url(lineup.pk))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(RaceLineup.objects.filter(pk=lineup.pk).exists())

    # --- Update blocked ---

    def test_patch_lineup_method_not_allowed(self):
        lineup = RaceLineup.objects.create(race=self.race, race_entry=self.race_entry)

        auth_client(self.client, self.team_owner)
        response = self.client.patch(
            self.detail_url(lineup.pk), {"race_entry": self.race_entry.pk}
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)