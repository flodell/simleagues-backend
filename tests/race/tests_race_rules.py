from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from core.models.races.rules import RaceRulesTemplate

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
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.template.refresh_from_db()
        self.assertFalse(self.template.is_active)

    def test_hard_delete_removes_template(self):
        auth_client(self.client, self.owner)
        response = self.client.delete(f"{self.detail_url}?hard=true")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
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