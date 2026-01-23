
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from core.models.league import League
from core.models.championship import Championship
from core.models.game import Game

class LeagueAPITestCase(APITestCase):
    """Tests for League API endpoints"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()

        # Create test users
        self.user1 = User.objects.create_user(
            username='testuser1',
            email='test1@example.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )

        acc = Game.objects.create(name='Assetto corsa', short_name='acc')
        lmu = Game.objects.create(name='Le mans ultimate', short_name='lmu')
        # Create test leagues
        self.league1 = League.objects.create(
            name='acc League',
            game=acc,
            description='Acc racing league',
            creator=self.user1,
            is_active=True
        )

        self.league2 = League.objects.create(
            name='LMU League',
            game=lmu,
            description='GT racing league',
            creator=self.user2,
            is_active=True
        )

        self.inactive_league = League.objects.create(
            name='Old League',
            game=lmu,
            description='Inactive league',
            creator=self.user1,
            is_active=False
        )

    def test_list_leagues(self):
        """Test listing all active leagues"""
        url = reverse('league-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)  # Only active leagues

        # Check that inactive league is not included
        league_names = [league['name'] for league in response.data["results"]]
        self.assertIn('acc League', league_names)
        self.assertIn('LMU League', league_names)
        self.assertNotIn('Old League', league_names)

    # def test_retrieve_league(self):
    #     """Test retrieving a single league by slug"""
    #     url = reverse('league-detail', kwargs={'slug': self.league1.slug})
    #     response = self.client.get(url)
    #
    #     self.assertEqual(response.status_code, status.HTTP_200_OK)
    #     self.assertEqual(response.data['name'], 'F1 League')
    #     self.assertEqual(response.data['game'], 'F1 24')
    #     self.assertEqual(response.data['description'], 'Formula 1 racing league')
    #     self.assertTrue(response.data['is_active'])
    #
    # def test_retrieve_nonexistent_league(self):
    #     """Test retrieving a league that doesn't exist"""
    #     url = reverse('league-detail', kwargs={'slug': 'nonexistent-league'})
    #     response = self.client.get(url)
    #
    #     self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    #
    # def test_create_league_authenticated(self):
    #     """Test creating a league while authenticated"""
    #     self.client.force_authenticate(user=self.user1)
    #
    #     url = reverse('league-list')
    #     data = {
    #         'name': 'New Racing League',
    #         'game': 'iRacing',
    #         'description': 'A brand new racing league',
    #         'is_active': True
    #     }
    #
    #     response = self.client.post(url, data, format='json')
    #
    #     self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    #     self.assertEqual(League.objects.count(), 4)
    #
    #     new_league = League.objects.get(slug='new-racing-league')
    #     self.assertEqual(new_league.name, 'New Racing League')
    #     self.assertEqual(new_league.created_by, self.user1)
    #     self.assertEqual(new_league.game, 'iRacing')
    #
    # def test_create_league_unauthenticated(self):
    #     """Test that unauthenticated users cannot create leagues"""
    #     url = reverse('league-list')
    #     data = {
    #         'name': 'Unauthorized League',
    #         'game': 'iRacing',
    #         'description': 'This should fail'
    #     }
    #
    #     response = self.client.post(url, data, format='json')
    #
    #     self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    #     self.assertEqual(League.objects.count(), 3)
    #
    # def test_update_league_by_admin(self):
    #     """Test updating a league by its owner"""
    #     self.client.force_authenticate(user=self.user1)
    #
    #     url = reverse('league-detail', kwargs={'slug': self.league1.slug})
    #     data = {
    #         'name': 'Updated F1 League',
    #         'description': 'Updated description',
    #         'game': 'F1 24',
    #         'is_active': True
    #     }
    #
    #     response = self.client.put(url, data, format='json')
    #
    #     self.assertEqual(response.status_code, status.HTTP_200_OK)
    #
    #     self.league1.refresh_from_db()
    #     self.assertEqual(self.league1.name, 'Updated F1 League')
    #     self.assertEqual(self.league1.description, 'Updated description')
    #
    # def test_update_league_by_member(self):
    #     """Test that non-owners cannot update a league"""
    #     self.client.force_authenticate(user=self.user2)
    #
    #     url = reverse('league-detail', kwargs={'slug': self.league1.slug})
    #     data = {
    #         'name': 'Hacked League',
    #         'description': 'This should fail',
    #         'game': 'F1 24',
    #         'is_active': True
    #     }
    #
    #     response = self.client.put(url, data, format='json')
    #
    #     self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    #
    #     self.league1.refresh_from_db()
    #     self.assertEqual(self.league1.name, 'F1 League')
    #     self.assertEqual(self.league1.description, 'Formula 1 racing league')
    #
    # def test_partial_update_league(self):
    #     """Test partial update (PATCH) of a league"""
    #     self.client.force_authenticate(user=self.user1)
    #
    #     url = reverse('league-detail', kwargs={'slug': self.league1.slug})
    #     data = {
    #         'description': 'Partially updated description'
    #     }
    #
    #     response = self.client.patch(url, data, format='json')
    #
    #     self.assertEqual(response.status_code, status.HTTP_200_OK)
    #
    #     self.league1.refresh_from_db()
    #     self.assertEqual(self.league1.description, 'Partially updated description')
    #     self.assertEqual(self.league1.name, 'F1 League')  # Unchanged
    #     self.assertEqual(self.league1.game, 'F1 24')  # Unchanged
    #
    # def test_delete_league_by_owner(self):
    #     self.client.force_authenticate(user=self.user1)
    #
    #     url = reverse('league-detail', kwargs={'slug': self.league1.slug})
    #     response = self.client.delete(url)
    #
    #     self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
    #     self.assertEqual(League.objects.filter(slug='f1-league').count(), 0)
    #     self.assertEqual(League.objects.count(), 2)
    #
    # def test_delete_league_by_non_owner(self):
    #     self.client.force_authenticate(user=self.user2)
    #
    #     url = reverse('league-detail', kwargs={'slug': self.league1.slug})
    #     response = self.client.delete(url)
    #
    #     self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    #     self.assertEqual(League.objects.filter(slug='f1-league').count(), 1)
    #     self.assertEqual(League.objects.count(), 3)
    #
    # def test_league_unique_slug(self):
    #     self.client.force_authenticate(user=self.user1)
    #
    #     url = reverse('league-list')
    #     data = {
    #         'name': 'Another League',
    #         'game': 'F1 24',
    #         'description': 'This should fail'
    #     }
    #
    #     response = self.client.post(url, data, format='json')
    #
    #     self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    #     self.assertIn('slug', response.data)
    #
    # def test_league_filtering_by_game(self):
    #     """Test filtering leagues by game"""
    #     url = reverse('league-list') + '?game=F1 24'
    #     response = self.client.get(url)
    #
    #     self.assertEqual(response.status_code, status.HTTP_200_OK)
    #     self.assertEqual(len(response.data), 1)
    #     self.assertEqual(response.data[0]['game'], 'F1 24')
    #     self.assertEqual(response.data[0]['name'], 'F1 League')
    #
    # def test_league_search_by_name(self):
    #     """Test searching leagues by name"""
    #     url = reverse('league-list') + '?search=F1'
    #     response = self.client.get(url)
    #
    #     self.assertEqual(response.status_code, status.HTTP_200_OK)
    #     self.assertEqual(len(response.data), 1)
    #     self.assertEqual(response.data[0]['name'], 'F1 League')
    #
    # def test_league_search_by_description(self):
    #     """Test searching leagues by description"""
    #     url = reverse('league-list') + '?search=GT racing'
    #     response = self.client.get(url)
    #
    #     self.assertEqual(response.status_code, status.HTTP_200_OK)
    #     self.assertEqual(len(response.data), 1)
    #     self.assertEqual(response.data[0]['name'], 'GT League')
    #
    # def test_league_ordering_by_name_ascending(self):
    #     """Test ordering leagues by name (A-Z)"""
    #     url = reverse('league-list') + '?ordering=name'
    #     response = self.client.get(url)
    #
    #     self.assertEqual(response.status_code, status.HTTP_200_OK)
    #     self.assertEqual(response.data[0]['name'], 'F1 League')
    #     self.assertEqual(response.data[1]['name'], 'GT League')
    #
    #
    # def test_league_ordering_by_created_at(self):
    #     """Test ordering leagues by creation date"""
    #     url = reverse('league-list') + '?ordering=created_at'
    #     response = self.client.get(url)
    #
    #     self.assertEqual(response.status_code, status.HTTP_200_OK)
    #     # First created should be first
    #     self.assertEqual(response.data[0]['slug'], 'f1-league')
    #
    # def test_create_league_without_required_fields(self):
    #     """Test creating a league without required fields"""
    #     self.client.force_authenticate(user=self.user1)
    #
    #     url = reverse('league-list')
    #     data = {
    #         'name': 'Incomplete League'
    #         # Missing slug, game
    #     }
    #
    #     response = self.client.post(url, data, format='json')
    #
    #     self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    #     self.assertIn('game', response.data)
    #
    # def test_deactivate_league(self):
    #     self.client.force_authenticate(user=self.user1)
    #
    #     url = reverse('league-detail', kwargs={'slug': self.league1.slug})
    #     data = {
    #         'is_active': False
    #     }
    #
    #     response = self.client.patch(url, data, format='json')
    #
    #     self.assertEqual(response.status_code, status.HTTP_200_OK)
    #
    #     self.league1.refresh_from_db()
    #     self.assertFalse(self.league1.is_active)
    #
    #     # Verify it doesn't appear in list anymore
    #     list_url = reverse('league-list')
    #     list_response = self.client.get(list_url)
    #     league_names = [league['name'] for league in list_response.data]
    #     self.assertNotIn('F1 League', league_names)