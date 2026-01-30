from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from core.models.car import Car
from core.models.championship import Championship, Team, Driver
from core.models.choices import (
    LeagueVisibility,
    LeagueMemberRole,
    ChampionshipStatus,
    ParticipantType,
    CarCategory,
)
from core.models.game import Game
from core.models.league import League, LeagueMembership


class ChampionshipAPITestCase(APITestCase):
    """Tests for Championship API endpoints"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()

        # Create test users
        self.admin_user = User.objects.create_user(
            username="admin", email="admin@example.com", password="testpass123"
        )
        self.staff_user = User.objects.create_user(
            username="staff", email="staff@example.com", password="testpass123"
        )
        self.team_owner = User.objects.create_user(
            username="team", email="teamowner@exemple.com", password="testpass123"
        )
        self.member_user = User.objects.create_user(
            username="member", email="member@example.com", password="testpass123"
        )
        self.outsider_user = User.objects.create_user(
            username="outsider", email="outsider@example.com", password="testpass123"
        )

        # Create game and cars
        self.game = Game.objects.create(name="Le Mans Ultimate", short_name="lmu")
        self.car = Car.objects.create(
            game=self.game,
            name="911 GT3 R",
            manufacturer="Porsche",
            category=CarCategory.LMGT3,
            year=2024,
        )

        # Create public league with memberships
        self.public_league = League.objects.create(
            name="Public League",
            game=self.game,
            creator=self.admin_user,
            visibility=LeagueVisibility.PUBLIC,
            is_active=True,
        )
        LeagueMembership.objects.create(
            league=self.public_league, user=self.admin_user, role=LeagueMemberRole.ADMIN
        )
        LeagueMembership.objects.create(
            league=self.public_league,
            user=self.staff_user,
            role=LeagueMemberRole.MODERATOR,
        )
        LeagueMembership.objects.create(
            league=self.public_league,
            user=self.member_user,
            role=LeagueMemberRole.MEMBER,
        )
        LeagueMembership.objects.create(
            league=self.public_league,
            user=self.team_owner,
            role=LeagueMemberRole.MEMBER,
        )

        # Create championships
        self.individual_champ = Championship.objects.create(
            league=self.public_league,
            name="Individual Championship",
            season="2025",
            start_date="2025-01-01",
            participant_type=ParticipantType.INDIVIDUAL,
            status=ChampionshipStatus.UPCOMING,
            max_participants=20,
        )

        self.team_champ = Championship.objects.create(
            league=self.public_league,
            name="Team Championship",
            season="2025",
            start_date="2025-01-01",
            participant_type=ParticipantType.TEAM,
            status=ChampionshipStatus.UPCOMING,
        )

    def test_list_and_filter_championships(self):
        """Test listing and filtering championships"""
        url = reverse("championship-list")

        # Unauthenticated - sees public only
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

        # Filter by participant type

        response = self.client.get(url, {"participant_type": ParticipantType.TEAM})
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["name"], "Team Championship")

        # Search by name
        response = self.client.get(url, {"search": "Individual"})
        self.assertEqual(response.data["count"], 1)

    def test_create_championship_permissions(self):
        """Test championship creation with different permission levels"""
        url = reverse("championship-list")
        data = {
            "name": "New Championship",
            "league": self.public_league.id,
            "participant_type": ParticipantType.INDIVIDUAL,
            "start_date": "2026-01-01",
        }

        # Non-admin cannot create
        self.client.force_authenticate(user=self.member_user)
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Admin can create
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Validation: short name fails
        data["name"] = "AB"
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Validation: end_date before start_date fails
        data["name"] = "Valid Name"
        data["end_date"] = "2025-01-01"
        response = self.client.post(url, data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_driver_registration_flow(self):
        """Test the full driver registration/unregistration flow"""
        register_url = reverse(
            "championship-register", kwargs={"pk": self.individual_champ.pk}
        )
        unregister_url = reverse(
            "championship-unregister", kwargs={"pk": self.individual_champ.pk}
        )

        self.client.force_authenticate(user=self.member_user)

        # Register successfully
        response = self.client.post(
            register_url, {"car": self.car.id, "racing_number": 42}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["racing_number"], 42)

        # Cannot register twice
        response = self.client.post(
            register_url, {"car": self.car.id, "racing_number": 43}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Unregister successfully
        response = self.client.post(unregister_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Driver.objects.filter(user=self.member_user).exists())

        # Cannot unregister if not registered
        response = self.client.post(unregister_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_registration_restrictions(self):
        """Test registration restrictions (status, max participants, team requirement)"""
        self.client.force_authenticate(user=self.member_user)

        # Cannot register for completed championship
        self.individual_champ.status = ChampionshipStatus.COMPLETED
        self.individual_champ.save()
        url = reverse("championship-register", kwargs={"pk": self.individual_champ.pk})
        response = self.client.post(
            url, {"car": self.car.id, "racing_number": 42}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Reset and test max participants
        self.individual_champ.status = ChampionshipStatus.UPCOMING
        self.individual_champ.max_participants = 1
        self.individual_champ.save()
        Driver.objects.create(
            championship=self.individual_champ,
            user=self.staff_user,
            car=self.car,
            racing_number=1,
        )
        response = self.client.post(
            url, {"car": self.car.id, "racing_number": 42}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Team championship requires team
        url = reverse("championship-register", kwargs={"pk": self.team_champ.pk})
        response = self.client.post(
            url, {"car": self.car.id, "racing_number": 42}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("team", response.data["detail"].lower())

    def test_team_management(self):
        """Test team creation, listing, and removal"""
        teams_url = reverse("championship-teams", kwargs={"pk": self.team_champ.pk})
        add_url = reverse("championship-add-team", kwargs={"pk": self.team_champ.pk})
        remove_url = reverse(
            "championship-remove-team", kwargs={"pk": self.team_champ.pk}
        )

        # Staff can add team (owner defaults to current user)
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.post(
            add_url,
            {
                "name": "Team Alpha",
                "racing_number": 42,
                "car": self.car.id,
                "owner": self.team_owner.id,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["owner"], self.team_owner.id)
        team_id = response.data["id"]

        # List teams
        response = self.client.get(teams_url)
        self.assertEqual(len(response.data), 1)

        # Member cannot add team
        self.client.force_authenticate(user=self.member_user)
        response = self.client.post(
            add_url,
            {"name": "Team Beta", "racing_number": 99, "car": self.car.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Non-owner cannot remove team
        response = self.client.post(remove_url, {"team_id": team_id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Owner can remove their team
        self.client.force_authenticate(user=self.team_owner)
        response = self.client.post(remove_url, {"team_id": team_id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_team_removal_restrictions(self):
        """Test team removal restrictions"""
        team = Team.objects.create(
            championship=self.team_champ,
            owner=self.member_user,
            name="Test Team",
            racing_number=42,
            car=self.car,
        )
        remove_url = reverse(
            "championship-remove-team", kwargs={"pk": self.team_champ.pk}
        )

        self.client.force_authenticate(user=self.member_user)

        # Cannot remove from active championship
        self.team_champ.status = ChampionshipStatus.ACTIVE
        self.team_champ.save()
        response = self.client.post(remove_url, {"team_id": team.id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Staff can remove any team (when not active)
        self.team_champ.status = ChampionshipStatus.UPCOMING
        self.team_champ.save()
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.post(remove_url, {"team_id": team.id}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_status_update(self):
        """Test championship status updates"""
        url = reverse(
            "championship-update-status", kwargs={"pk": self.individual_champ.pk}
        )

        # Non-admin cannot update
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.post(
            url, {"status": ChampionshipStatus.ACTIVE}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Admin can update
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            url, {"status": ChampionshipStatus.ACTIVE}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.individual_champ.refresh_from_db()
        self.assertEqual(self.individual_champ.status, ChampionshipStatus.ACTIVE)

        # Invalid status fails
        response = self.client.post(url, {"status": "INVALID"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_add_team_to_individual_championship(self):
        """Test that teams cannot be added to individual championships"""
        url = reverse("championship-add-team", kwargs={"pk": self.individual_champ.pk})
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.post(
            url, {"name": "Team", "racing_number": 1, "car": self.car.id}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Also test listing teams on individual championship
        url = reverse("championship-teams", kwargs={"pk": self.individual_champ.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
