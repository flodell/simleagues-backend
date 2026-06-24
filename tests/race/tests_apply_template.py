# === Ajouts à coller dans tests_race_rules_template.py ===
# Ces tests utilisent un setUp plus riche que la classe CRUD existante,
# donc je propose une nouvelle classe dédiée dans le même fichier.

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
from core.models.races.rules import RaceRules, RaceRulesTemplate
from core.models.races.weather import RaceWeather
from core.models.track import Track

User = get_user_model()


def auth_client(client, user):
    token = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")


class RaceRulesTemplateApplyTests(APITestCase):

    def setUp(self):
        self.template_owner = User.objects.create_user(
            username="template_owner", password="pass"
        )
        self.race_creator = User.objects.create_user(
            username="race_creator", password="pass"
        )
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
            league=self.league,
            user=self.race_creator,
            role=LeagueMemberRole.ADMIN,
        )

        # Race + default RaceRules + 1 default RaceWeather
        self.race = Race.objects.create(
            name="Test Race",
            league=self.league,
            track=self.track,
            scheduled_date=timezone.now() + timedelta(days=7),
            visibility=RaceVisibility.PUBLIC,
            creator=self.race_creator,
        )
        self.rules = RaceRules.objects.create(race=self.race)
        self.stage_1 = RaceWeather.objects.create(
            rules=self.rules,
            order=1,
            duration_minutes=60,
            sky_condition=SkyCondition.CLEAR,
            ambient_temp=22,
            track_temp=28,
            rain_chance=0,
        )

        # Template owned by template_owner with non-default values
        self.template = RaceRulesTemplate.objects.create(
            name="Endurance Pro",
            created_by=self.template_owner,
            fuel_usage="X3",
            tire_wear="X2",
            tire_warmers=False,
            mechanical_failures="TIME_SCALED",
            flag_rules="PARTIAL",
            track_limits="STRICT",
            track_limits_points=5,
            is_dynamic=True,
        )

        self.apply_url = reverse(
            "race-rules-template-apply", kwargs={"pk": self.template.pk}
        )

    # --- Success ---

    def test_apply_template_success(self):
        # template_owner is also the one applying — but the race creator check is separate.
        # Use race_creator who owns the race. They need their own template to apply it.
        own_template = RaceRulesTemplate.objects.create(
            name="My Template",
            created_by=self.race_creator,
            fuel_usage="X3",
            is_dynamic=True,
        )
        url = reverse("race-rules-template-apply", kwargs={"pk": own_template.pk})

        auth_client(self.client, self.race_creator)
        response = self.client.post(url, {"race_id": self.race.pk}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_apply_template_copies_all_fields(self):
        # template_owner owns the template AND is a league admin (so can manage the race)
        LeagueMembership.objects.create(
            league=self.league,
            user=self.template_owner,
            role=LeagueMemberRole.ADMIN,
        )

        auth_client(self.client, self.template_owner)
        response = self.client.post(
            self.apply_url, {"race_id": self.race.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.rules.refresh_from_db()
        self.assertEqual(self.rules.fuel_usage, "X3")
        self.assertEqual(self.rules.tire_wear, "X2")
        self.assertFalse(self.rules.tire_warmers)
        self.assertEqual(self.rules.mechanical_failures, "TIME_SCALED")
        self.assertEqual(self.rules.flag_rules, "PARTIAL")
        self.assertEqual(self.rules.track_limits, "STRICT")
        self.assertEqual(self.rules.track_limits_points, 5)
        self.assertTrue(self.rules.is_dynamic)

    # --- Permissions ---

    def test_apply_template_no_race_permission(self):
        # template_owner owns the template but cannot manage the race (not creator, not staff).
        auth_client(self.client, self.template_owner)
        response = self.client.post(
            self.apply_url, {"race_id": self.race.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_apply_template_not_owned(self):
        # outsider tries to apply someone else's template -> 404 (queryset filters it out)
        auth_client(self.client, self.outsider)
        response = self.client.post(
            self.apply_url, {"race_id": self.race.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # --- Cross-model validation ---

    def test_apply_static_template_blocked_with_multiple_stages(self):
        # Race has 2 stages and is_dynamic=True; try to apply a static (is_dynamic=False) template.
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

        # Create a static template owned by race_creator
        static_template = RaceRulesTemplate.objects.create(
            name="Static Template",
            created_by=self.race_creator,
            is_dynamic=False,
        )
        url = reverse(
            "race-rules-template-apply", kwargs={"pk": static_template.pk}
        )

        auth_client(self.client, self.race_creator)
        response = self.client.post(url, {"race_id": self.race.pk}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)