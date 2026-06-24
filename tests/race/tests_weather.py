from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from core.models.choices import (
    LeagueMemberRole,
    LeagueVisibility,
    RaceVisibility,
    SkyCondition,
)
from core.models.game import Game
from core.models.league import League, LeagueMembership
from core.models.races.race import Race
from core.models.races.rules import RaceRules
from core.models.races.weather import RaceWeather
from core.models.track import Track

User = get_user_model()


def auth_client(client, user):
    token = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")


def make_stage(rules, order, sky=SkyCondition.CLEAR, rain=0):
    return RaceWeather.objects.create(
        rules=rules,
        order=order,
        duration_minutes=30,
        sky_condition=sky,
        ambient_temp=22,
        track_temp=28,
        rain_chance=rain,
    )


class RaceWeatherViewSetTests(APITestCase):

    def setUp(self):
        self.creator = User.objects.create_user(username="creator", password="pass")
        self.league_admin = User.objects.create_user(username="admin", password="pass")
        self.league_member = User.objects.create_user(username="member", password="pass")
        self.outsider = User.objects.create_user(username="outsider", password="pass")

        self.game = Game.objects.create(name="Le Mans Ultimate")
        self.track = Track.objects.create(
            game=self.game, name="Spa-Francorchamps", corners=20
        )

        self.league = League.objects.create(
            name="Test League",
            visibility=LeagueVisibility.PUBLIC,
            game=self.game,
        )
        LeagueMembership.objects.create(
            league=self.league, user=self.league_admin, role=LeagueMemberRole.ADMIN
        )
        LeagueMembership.objects.create(
            league=self.league, user=self.league_member, role=LeagueMemberRole.MEMBER
        )

        self.race = Race.objects.create(
            name="Test Race",
            league=self.league,
            track=self.track,
            scheduled_date=timezone.now() + timedelta(days=7),
            visibility=RaceVisibility.PUBLIC,
            creator=self.creator,
        )
        self.rules = RaceRules.objects.create(race=self.race)
        # 1 default stage to mirror ensure_race_rules_and_weather behavior
        self.stage_1 = make_stage(self.rules, order=1)

        self.list_url = reverse(
            "race-weather-list", kwargs={"race_pk": self.race.pk}
        )

    def detail_url(self, stage_pk):
        return reverse(
            "race-weather-detail",
            kwargs={"race_pk": self.race.pk, "pk": stage_pk},
        )

    # --- Create ---

    def test_create_stage_auto_assigns_sequential_order(self):
        # Enable dynamic so we can add a 2nd stage
        self.rules.is_dynamic = True
        self.rules.save()

        auth_client(self.client, self.creator)
        response = self.client.post(
            self.list_url,
            {
                "duration_minutes": 45,
                "sky_condition": SkyCondition.OVERCAST,
                "ambient_temp": 20,
                "track_temp": 25,
                "rain_chance": 30,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["order"], 2)

    def test_create_stage_blocked_when_static(self):
        # is_dynamic=False by default, 1 stage already exists
        auth_client(self.client, self.creator)
        response = self.client.post(
            self.list_url,
            {
                "duration_minutes": 30,
                "sky_condition": SkyCondition.CLEAR,
                "ambient_temp": 22,
                "track_temp": 28,
                "rain_chance": 0,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_stage_blocked_beyond_max(self):
        self.rules.is_dynamic = True
        self.rules.save()
        # Fill up to MAX_STAGES (5 total = 1 existing + 4 new)
        for order in range(2, RaceWeather.MAX_STAGES + 1):
            make_stage(self.rules, order=order)

        auth_client(self.client, self.creator)
        response = self.client.post(
            self.list_url,
            {
                "duration_minutes": 30,
                "sky_condition": SkyCondition.CLEAR,
                "ambient_temp": 22,
                "track_temp": 28,
                "rain_chance": 0,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- Visibility ---

    def test_list_private_race_as_outsider(self):
        self.race.visibility = RaceVisibility.PRIVATE
        self.race.save()

        auth_client(self.client, self.outsider)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # --- Permissions ---

    def test_create_as_league_member_forbidden(self):
        self.rules.is_dynamic = True
        self.rules.save()

        auth_client(self.client, self.league_member)
        response = self.client.post(
            self.list_url,
            {
                "duration_minutes": 30,
                "sky_condition": SkyCondition.CLEAR,
                "ambient_temp": 22,
                "track_temp": 28,
                "rain_chance": 0,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # --- Update ---

    def test_patch_stage_as_creator(self):
        auth_client(self.client, self.creator)
        response = self.client.patch(
            self.detail_url(self.stage_1.pk),
            {"ambient_temp": 30, "rain_chance": 50},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.stage_1.refresh_from_db()
        self.assertEqual(self.stage_1.ambient_temp, 30)
        self.assertEqual(self.stage_1.rain_chance, 50)

    # --- Delete ---

    def test_delete_only_stage_blocked(self):
        auth_client(self.client, self.creator)
        response = self.client.delete(self.detail_url(self.stage_1.pk))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(RaceWeather.objects.filter(pk=self.stage_1.pk).exists())

    def test_delete_middle_stage_renumbers(self):
        self.rules.is_dynamic = True
        self.rules.save()
        stage_2 = make_stage(self.rules, order=2, sky=SkyCondition.OVERCAST)
        stage_3 = make_stage(self.rules, order=3, sky=SkyCondition.LIGHT_RAIN)

        auth_client(self.client, self.creator)
        response = self.client.delete(self.detail_url(stage_2.pk))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # stage_3 should now be order=2
        stage_3.refresh_from_db()
        self.assertEqual(stage_3.order, 2)
        # stage_1 unchanged
        self.stage_1.refresh_from_db()
        self.assertEqual(self.stage_1.order, 1)