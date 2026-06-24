from datetime import timedelta

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Game, Track, League, LeagueMembership, Race, RaceWeather
from core.models.choices import LeagueVisibility, LeagueMemberRole, RaceVisibility, SkyCondition
from core.models.races.rules import RaceRulesTemplate, RaceRules

User = get_user_model()


def auth_client(client, user):
    """Helper to authenticate a test client with JWT."""
    token = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")


class RaceRulesTemplateTests(APITestCase):

    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="pass")
        self.other = User.objects.create_user(username="other", password="pass")

        self.template = RaceRulesTemplate.objects.create(
            name="My Template", created_by=self.owner
        )

        self.list_url = reverse("race-rules-template-list")
        self.detail_url = reverse(
            "race-rules-template-detail", kwargs={"pk": self.template.pk}
        )
        self.duplicate_url = reverse(
            "race-rules-template-duplicate", kwargs={"pk": self.template.pk}
        )

    # --- CRUD ---

    def test_create_unauthenticated(self):
        response = self.client.post(self.list_url, {"name": "New Template"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_sets_created_by(self):
        auth_client(self.client, self.other)
        response = self.client.post(self.list_url, {"name": "New Template"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        template = RaceRulesTemplate.objects.get(name="New Template")
        self.assertEqual(template.created_by, self.other)

    def test_user_cannot_see_other_users_templates(self):
        auth_client(self.client, self.other)
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_as_non_owner(self):
        auth_client(self.client, self.other)
        response = self.client.patch(self.detail_url, {"fuel_usage": "X3"})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # --- Delete ---

    def test_soft_delete_archives_template(self):
        auth_client(self.client, self.owner)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.template.refresh_from_db()
        self.assertFalse(self.template.is_active)

    def test_hard_delete_removes_template(self):
        auth_client(self.client, self.owner)
        response = self.client.delete(f"{self.detail_url}?hard=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(RaceRulesTemplate.objects.filter(pk=self.template.pk).exists())

    # --- Filtering ---

    def test_list_excludes_archived(self):
        archived = RaceRulesTemplate.objects.create(
            name="Archived", created_by=self.owner, is_active=False
        )
        auth_client(self.client, self.owner)
        response = self.client.get(self.list_url)
        results = response.data["results"] if "results" in response.data else response.data
        ids = [item["id"] for item in results]
        self.assertIn(self.template.pk, ids)
        self.assertNotIn(archived.pk, ids)

    def test_list_includes_archived_with_param(self):
        archived = RaceRulesTemplate.objects.create(
            name="Archived", created_by=self.owner, is_active=False
        )
        auth_client(self.client, self.owner)
        response = self.client.get(f"{self.list_url}?include_archived=true")
        results = response.data["results"] if "results" in response.data else response.data
        ids = [item["id"] for item in results]
        self.assertIn(archived.pk, ids)

    # --- Validation ---

    def test_duplicate_name_blocked_for_same_user(self):
        auth_client(self.client, self.owner)
        response = self.client.post(self.list_url, {"name": "My Template"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- Duplicate action ---

    def test_duplicate_creates_copy(self):
        self.template.fuel_usage = "X3"
        self.template.is_dynamic = True
        self.template.save()

        auth_client(self.client, self.owner)
        response = self.client.post(self.duplicate_url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "My Template (copy)")
        self.assertEqual(response.data["fuel_usage"], "X3")
        self.assertTrue(response.data["is_dynamic"])

    def test_duplicate_increments_name(self):
        auth_client(self.client, self.owner)
        self.client.post(self.duplicate_url)
        response = self.client.post(self.duplicate_url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "My Template (copy) 2")


class RaceRulesViewTests(APITestCase):

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
            name="Test League", visibility=LeagueVisibility.PUBLIC, game=self.game
        )
        LeagueMembership.objects.create(
            league=self.league, user=self.league_admin, role=LeagueMemberRole.ADMIN
        )
        LeagueMembership.objects.create(
            league=self.league, user=self.league_member, role=LeagueMemberRole.MEMBER
        )

        # Public race in the league, created by `creator` (who is NOT a league member)
        self.race = Race.objects.create(
            name="Test Race",
            league=self.league,
            track=self.track,
            scheduled_date=timezone.now() + timedelta(days=7),
            visibility=RaceVisibility.PUBLIC,
            creator=self.creator,
        )
        self.rules = RaceRules.objects.create(race=self.race)
        RaceWeather.objects.create(
            rules=self.rules,
            order=1,
            duration_minutes=60,
            sky_condition=SkyCondition.CLEAR,
            ambient_temp=22,
            track_temp=28,
            rain_chance=0,
        )

        self.url = reverse("race-rules", kwargs={"race_pk": self.race.pk})

    # --- Read (visibility) ---

    def test_get_public_race_rules_as_any_user(self):
        auth_client(self.client, self.outsider)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["race"], self.race.pk)

    def test_get_private_race_rules_as_non_member(self):
        self.race.visibility = RaceVisibility.PRIVATE
        self.race.save()

        auth_client(self.client, self.outsider)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_private_race_rules_as_league_member(self):
        self.race.visibility = RaceVisibility.PRIVATE
        self.race.save()

        auth_client(self.client, self.league_member)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # --- Write (permissions) ---

    def test_patch_as_creator(self):
        auth_client(self.client, self.creator)
        response = self.client.patch(self.url, {"fuel_usage": "X3"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.rules.refresh_from_db()
        self.assertEqual(self.rules.fuel_usage, "X3")

    def test_patch_as_league_admin(self):
        auth_client(self.client, self.league_admin)
        response = self.client.patch(self.url, {"fuel_usage": "X3"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_patch_as_league_member_forbidden(self):
        auth_client(self.client, self.league_member)
        response = self.client.patch(self.url, {"fuel_usage": "X3"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # --- Write (cross-model validation) ---

    def test_patch_disable_dynamic_with_multiple_stages_blocked(self):
        # Enable dynamic and add a second stage
        self.rules.is_dynamic = True
        self.rules.save()
        RaceWeather.objects.create(
            rules=self.rules,
            order=2,
            duration_minutes=30,
            sky_condition=SkyCondition.OVERCAST,
            ambient_temp=20,
            track_temp=25,
            rain_chance=20,
        )

        auth_client(self.client, self.creator)
        response = self.client.patch(self.url, {"is_dynamic": False})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("is_dynamic", response.data)