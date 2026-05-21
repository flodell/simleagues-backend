from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from core.models.choices import TeamRole, TeamJoinRequestStatus
from core.models.team import Team, TeamMembership, TeamJoinRequest

User = get_user_model()


def auth_client(client, user):
    """Helper to authenticate a test client with JWT."""
    token = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")


class TeamCRUDTests(APITestCase):

    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="pass")
        self.manager = User.objects.create_user(username="manager", password="pass")
        self.other = User.objects.create_user(username="other", password="pass")

        self.team = Team.objects.create(name="Red Racing", description="A test team")
        TeamMembership.objects.create(
            team=self.team, user=self.owner, role=TeamRole.OWNER
        )
        TeamMembership.objects.create(
            team=self.team, user=self.manager, role=TeamRole.MANAGER
        )

        self.list_url = reverse("team-list")
        self.detail_url = reverse("team-detail", kwargs={"pk": self.team.pk})

    def test_create_team_unauthenticated(self):
        response = self.client.post(self.list_url, {"name": "New Team"})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_team_creates_owner_membership(self):
        auth_client(self.client, self.other)
        response = self.client.post(self.list_url, {"name": "New Team"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        team = Team.objects.get(name="New Team")
        self.assertTrue(
            TeamMembership.objects.filter(
                team=team, user=self.other, role=TeamRole.OWNER
            ).exists()
        )

    def test_create_team_name_too_short(self):
        auth_client(self.client, self.other)
        response = self.client.post(self.list_url, {"name": "AB"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve_returns_detail_fields(self):
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for field in ["total_races", "total_wins", "total_podiums", "updated_at"]:
            self.assertIn(field, response.data)

    def test_update_as_owner(self):
        auth_client(self.client, self.owner)
        response = self.client.patch(self.detail_url, {"name": "Blue Racing"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_as_manager(self):
        auth_client(self.client, self.manager)
        response = self.client.patch(self.detail_url, {"name": "Blue Racing"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_as_non_member(self):
        auth_client(self.client, self.other)
        response = self.client.patch(self.detail_url, {"name": "Blue Racing"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_soft_delete_archives_team(self):
        auth_client(self.client, self.owner)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.team.refresh_from_db()
        self.assertFalse(self.team.is_active)

    def test_hard_delete_removes_team(self):
        auth_client(self.client, self.owner)
        response = self.client.delete(f"{self.detail_url}?hard_delete=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Team.objects.filter(pk=self.team.pk).exists())

    def test_delete_as_non_owner(self):
        auth_client(self.client, self.manager)
        response = self.client.delete(self.detail_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class TeamJoinRequestTests(APITestCase):

    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="pass")
        self.manager = User.objects.create_user(username="manager", password="pass")
        self.applicant = User.objects.create_user(username="applicant", password="pass")
        self.other = User.objects.create_user(username="other", password="pass")

        self.team = Team.objects.create(name="Red Racing")
        TeamMembership.objects.create(
            team=self.team, user=self.owner, role=TeamRole.OWNER
        )
        TeamMembership.objects.create(
            team=self.team, user=self.manager, role=TeamRole.MANAGER
        )

        self.join_url = reverse("team-join-request", kwargs={"pk": self.team.pk})
        self.cancel_url = reverse("team-cancel-request", kwargs={"pk": self.team.pk})
        self.approve_url = reverse("team-approve-request", kwargs={"pk": self.team.pk})
        self.reject_url = reverse("team-reject-request", kwargs={"pk": self.team.pk})

    # --- join_request ---

    def test_join_request_created(self):
        auth_client(self.client, self.applicant)
        response = self.client.post(self.join_url)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            TeamJoinRequest.objects.filter(
                team=self.team,
                user=self.applicant,
                status=TeamJoinRequestStatus.PENDING,
            ).exists()
        )

    def test_join_request_already_member(self):
        auth_client(self.client, self.manager)
        response = self.client.post(self.join_url)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)

    def test_join_request_already_pending(self):
        TeamJoinRequest.objects.create(
            team=self.team, user=self.applicant, status=TeamJoinRequestStatus.PENDING
        )
        auth_client(self.client, self.applicant)
        response = self.client.post(self.join_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- cancel_request ---

    def test_cancel_request(self):
        join_request = TeamJoinRequest.objects.create(
            team=self.team, user=self.applicant, status=TeamJoinRequestStatus.PENDING
        )
        auth_client(self.client, self.applicant)
        response = self.client.post(self.cancel_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        join_request.refresh_from_db()
        self.assertEqual(join_request.status, TeamJoinRequestStatus.CANCELLED)

    def test_cancel_request_no_pending(self):
        auth_client(self.client, self.applicant)
        response = self.client.post(self.cancel_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # --- approve_request ---

    def test_approve_request_as_owner(self):
        join_request = TeamJoinRequest.objects.create(
            team=self.team, user=self.applicant, status=TeamJoinRequestStatus.PENDING
        )
        auth_client(self.client, self.owner)
        response = self.client.post(
            self.approve_url, {"request_id": join_request.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            TeamMembership.objects.filter(team=self.team, user=self.applicant).exists()
        )

    def test_approve_request_as_manager(self):
        join_request = TeamJoinRequest.objects.create(
            team=self.team, user=self.applicant, status=TeamJoinRequestStatus.PENDING
        )
        auth_client(self.client, self.manager)
        response = self.client.post(
            self.approve_url, {"request_id": join_request.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_approve_request_as_non_member(self):
        join_request = TeamJoinRequest.objects.create(
            team=self.team, user=self.applicant, status=TeamJoinRequestStatus.PENDING
        )
        auth_client(self.client, self.other)
        response = self.client.post(
            self.approve_url, {"request_id": join_request.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # --- reject_request ---

    def test_reject_request_as_owner(self):
        join_request = TeamJoinRequest.objects.create(
            team=self.team, user=self.applicant, status=TeamJoinRequestStatus.PENDING
        )
        auth_client(self.client, self.owner)
        response = self.client.post(
            self.reject_url, {"request_id": join_request.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        join_request.refresh_from_db()
        self.assertEqual(join_request.status, TeamJoinRequestStatus.REJECTED)

    def test_reject_request_as_non_member(self):
        join_request = TeamJoinRequest.objects.create(
            team=self.team, user=self.applicant, status=TeamJoinRequestStatus.PENDING
        )
        auth_client(self.client, self.other)
        response = self.client.post(
            self.reject_url, {"request_id": join_request.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class TeamMembershipActionTests(APITestCase):

    def setUp(self):
        self.owner = User.objects.create_user(username="owner", password="pass")
        self.manager = User.objects.create_user(username="manager", password="pass")
        self.driver = User.objects.create_user(username="driver", password="pass")
        self.other = User.objects.create_user(username="other", password="pass")

        self.team = Team.objects.create(name="Red Racing")
        TeamMembership.objects.create(
            team=self.team, user=self.owner, role=TeamRole.OWNER
        )
        TeamMembership.objects.create(
            team=self.team, user=self.manager, role=TeamRole.MANAGER
        )
        TeamMembership.objects.create(
            team=self.team, user=self.driver, role=TeamRole.DRIVER
        )

        self.leave_url = reverse("team-leave", kwargs={"pk": self.team.pk})
        self.kick_url = reverse("team-kick", kwargs={"pk": self.team.pk})
        self.set_role_url = reverse("team-set-role", kwargs={"pk": self.team.pk})
        self.transfer_url = reverse(
            "team-transfer-ownership", kwargs={"pk": self.team.pk}
        )

    # --- leave ---

    def test_leave_as_member(self):
        auth_client(self.client, self.driver)
        response = self.client.post(self.leave_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(
            TeamMembership.objects.filter(team=self.team, user=self.driver).exists()
        )

    def test_leave_as_owner_blocked(self):
        auth_client(self.client, self.owner)
        response = self.client.post(self.leave_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_leave_as_non_member(self):
        auth_client(self.client, self.other)
        response = self.client.post(self.leave_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- kick ---

    def test_kick_driver_as_owner(self):
        auth_client(self.client, self.owner)
        response = self.client.post(
            self.kick_url, {"user_id": self.driver.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(
            TeamMembership.objects.filter(team=self.team, user=self.driver).exists()
        )

    def test_kick_driver_as_manager(self):
        auth_client(self.client, self.manager)
        response = self.client.post(
            self.kick_url, {"user_id": self.driver.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_kick_manager_as_manager_blocked(self):
        manager2 = User.objects.create_user(username="manager2", password="pass")
        TeamMembership.objects.create(
            team=self.team, user=manager2, role=TeamRole.MANAGER
        )
        auth_client(self.client, self.manager)
        response = self.client.post(
            self.kick_url, {"user_id": manager2.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_kick_owner_blocked(self):
        auth_client(self.client, self.manager)
        response = self.client.post(
            self.kick_url, {"user_id": self.owner.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- set_role ---

    def test_set_role_owner_assigns_manager(self):
        auth_client(self.client, self.owner)
        response = self.client.post(
            self.set_role_url,
            {"user_id": self.driver.pk, "role": TeamRole.MANAGER},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            TeamMembership.objects.get(team=self.team, user=self.driver).role,
            TeamRole.MANAGER,
        )

    def test_set_role_manager_assigns_driver(self):
        reserve = User.objects.create_user(username="reserve", password="pass")
        TeamMembership.objects.create(
            team=self.team, user=reserve, role=TeamRole.RESERVE
        )
        auth_client(self.client, self.manager)
        response = self.client.post(
            self.set_role_url,
            {"user_id": reserve.pk, "role": TeamRole.DRIVER},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_set_role_manager_assigns_manager_blocked(self):
        auth_client(self.client, self.manager)
        response = self.client.post(
            self.set_role_url,
            {"user_id": self.driver.pk, "role": TeamRole.MANAGER},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_set_role_owner_blocked(self):
        auth_client(self.client, self.owner)
        response = self.client.post(
            self.set_role_url,
            {"user_id": self.driver.pk, "role": TeamRole.OWNER},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_set_role_on_owner_blocked(self):
        auth_client(self.client, self.owner)
        response = self.client.post(
            self.set_role_url,
            {"user_id": self.owner.pk, "role": TeamRole.MANAGER},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # --- transfer_ownership ---

    def test_transfer_ownership_as_owner(self):
        auth_client(self.client, self.owner)
        response = self.client.post(
            self.transfer_url, {"user_id": self.driver.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            TeamMembership.objects.get(team=self.team, user=self.driver).role,
            TeamRole.OWNER,
        )
        self.assertEqual(
            TeamMembership.objects.get(team=self.team, user=self.owner).role,
            TeamRole.MANAGER,
        )

    def test_transfer_ownership_to_non_member(self):
        auth_client(self.client, self.owner)
        response = self.client.post(
            self.transfer_url, {"user_id": self.other.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_transfer_ownership_as_non_owner(self):
        auth_client(self.client, self.manager)
        response = self.client.post(
            self.transfer_url, {"user_id": self.driver.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
