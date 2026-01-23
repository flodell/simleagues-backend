
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from core.models.choices import LeagueVisibility, LeagueMemberRole
from core.models.league import League, LeagueMembership
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
        self.user3 = User.objects.create_user(
            username='testuser3',
            email='test3@example.com',
            password='testpass123'
        )

        # Create games
        self.acc = Game.objects.create(name='Assetto Corsa', short_name='acc')
        self.lmu = Game.objects.create(name='Le Mans Ultimate', short_name='lmu')

        # Create test leagues
        self.league1 = League.objects.create(
            name='ACC League',
            game=self.acc,
            description='ACC racing league',
            creator=self.user1,
            visibility=LeagueVisibility.PUBLIC,
            is_active=True
        )
        LeagueMembership.objects.create(
            league=self.league1,
            user=self.user1,
            role=LeagueMemberRole.ADMIN
        )

        self.league2 = League.objects.create(
            name='LMU League',
            game=self.lmu,
            description='LMU racing league',
            creator=self.user2,
            visibility=LeagueVisibility.PUBLIC,
            is_active=True
        )
        LeagueMembership.objects.create(
            league=self.league2,
            user=self.user2,
            role=LeagueMemberRole.ADMIN
        )

        self.inactive_league = League.objects.create(
            name='Old League',
            game=self.lmu,
            description='Inactive league',
            creator=self.user1,
            visibility=LeagueVisibility.PUBLIC,
            is_active=False
        )
        LeagueMembership.objects.create(
            league=self.inactive_league,
            user=self.user1,
            role=LeagueMemberRole.ADMIN
        )

        # Create an INVITE_ONLY league
        self.invite_only_league = League.objects.create(
            name='Private Club',
            game=self.acc,
            description='Invite only league',
            creator=self.user1,
            visibility=LeagueVisibility.INVITE_ONLY,
            is_active=True
        )
        LeagueMembership.objects.create(
            league=self.invite_only_league,
            user=self.user1,
            role=LeagueMemberRole.ADMIN
        )

    # ===== LIST TESTS =====

    def test_list_leagues(self):
        """Test listing all active public leagues (unauthenticated)"""
        url = reverse('league-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)  # Only active public leagues

        league_names = [league['name'] for league in response.data["results"]]
        self.assertIn('ACC League', league_names)
        self.assertIn('LMU League', league_names)
        self.assertNotIn('Old League', league_names)
        self.assertNotIn('Private Club', league_names)


    def test_list_leagues_authenticated(self):
        """Test that authenticated users see public leagues + their own"""
        self.client.force_authenticate(user=self.user2)
        url = reverse('league-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should see: ACC League, LMU League
        self.assertEqual(response.data["count"], 3)

    def test_filter_leagues_by_game(self):
        """Test filtering leagues by game"""
        url = reverse('league-list')
        response = self.client.get(url, {'game': self.acc.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]['name'], 'ACC League')

    def test_search_leagues_by_name(self):
        """Test searching leagues by name"""
        url = reverse('league-list')
        response = self.client.get(url, {'search': 'ACC'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]['name'], 'ACC League')

    # ===== RETRIEVE TESTS =====

    def test_retrieve_league(self):
        """Test retrieving a single league by pk"""
        url = reverse('league-detail', kwargs={'pk': self.league1.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], self.league1.name)
        self.assertEqual(response.data['game'], self.acc.id)
        self.assertTrue(response.data['is_active'])

    def test_retrieve_nonexistent_league(self):
        """Test retrieving a league that doesn't exist"""
        url = reverse('league-detail', kwargs={'pk': -1})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_league_shows_user_role(self):
        """Test that retrieve shows user's role in league"""
        self.client.force_authenticate(user=self.user1)
        url = reverse('league-detail', kwargs={'pk': self.league1.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user_role'], LeagueMemberRole.ADMIN)

        # ===== CREATE TESTS =====

    def test_create_league_unauthenticated(self):
        """Test that unauthenticated users cannot create leagues"""
        url = reverse('league-list')
        data = {
            'name': 'New League',
            'description': 'Test league',
            'visibility': LeagueVisibility.PUBLIC,
            'game': self.acc.id
        }
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_league_authenticated(self):
        """Test creating a league as authenticated user"""
        self.client.force_authenticate(user=self.user3)
        url = reverse('league-list')
        data = {
            'name': 'New League',
            'description': 'Test league',
            'visibility': LeagueVisibility.PUBLIC,
            'game': self.lmu.id
        }
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New League')

        # Verify creator was added as admin
        league = League.objects.get(pk=response.data['id'])
        membership = LeagueMembership.objects.get(league=league, user=self.user3)
        self.assertEqual(membership.role, LeagueMemberRole.ADMIN)

    def test_create_league_with_short_name(self):
        """Test that league name must be at least 3 characters"""
        self.client.force_authenticate(user=self.user1)
        url = reverse('league-list')
        data = {
            'name': 'AB',  # Too short
            'description': 'Test',
            'visibility': LeagueVisibility.PUBLIC,
            'game': self.acc.id
        }
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_league_generates_invitation_code_for_invite_only(self):
        """Test that INVITE_ONLY leagues get an invitation code"""
        self.client.force_authenticate(user=self.user1)
        url = reverse('league-list')
        data = {
            'name': 'Secret League',
            'description': 'Invite only',
            'visibility': LeagueVisibility.INVITE_ONLY,
            'game': self.acc.id
        }
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        league = League.objects.get(pk=response.data['id'])
        self.assertIsNotNone(league.invitation_code)

    # ===== UPDATE TESTS =====

    def test_update_league_as_admin(self):
        """Test updating league as admin"""
        self.client.force_authenticate(user=self.user1)
        url = reverse('league-detail', kwargs={'pk': self.league1.pk})
        data = {
            'name': 'Updated ACC League',
            'description': 'Updated description',
            'visibility': LeagueVisibility.PUBLIC,
            'game': self.acc.id
        }
        response = self.client.patch(url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Updated ACC League')

    def test_update_league_as_non_staff(self):
        """Test that non-staff members cannot update league"""
        # Add user3 as regular member
        LeagueMembership.objects.create(
            league=self.league1,
            user=self.user3,
            role=LeagueMemberRole.MEMBER
        )

        self.client.force_authenticate(user=self.user3)
        url = reverse('league-detail', kwargs={'pk': self.league1.pk})
        data = {'name': 'Hacked League'}
        response = self.client.patch(url, data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_league_as_non_member(self):
        """Test that non-members cannot update league"""
        self.client.force_authenticate(user=self.user3)
        url = reverse('league-detail', kwargs={'pk': self.league1.pk})
        data = {'name': 'Hacked League'}
        response = self.client.patch(url, data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ===== DELETE/ARCHIVE TESTS =====

    def test_delete_league_archives_by_default(self):
        """Test that DELETE archives the league by default (soft delete)"""
        self.client.force_authenticate(user=self.user1)
        url = reverse('league-detail', kwargs={'pk': self.league1.pk})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # League still exists but is archived
        league = League.objects.get(pk=self.league1.pk)
        self.assertFalse(league.is_active)

    def test_delete_already_archived_league(self):
        """Test that archiving an already archived league fails"""
        self.league1.is_active = False
        self.league1.save()

        self.client.force_authenticate(user=self.user1)
        url = reverse('league-detail', kwargs={'pk': self.league1.pk})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already archived', response.data['detail'].lower())

    def test_hard_delete_without_confirmation(self):
        """Test that hard delete requires confirmation"""
        self.client.force_authenticate(user=self.user1)
        url = reverse('league-detail', kwargs={'pk': self.league1.pk}) + '?hard_delete=true'
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('confirm_delete', response.data['detail'])

    def test_hard_delete_with_wrong_confirmation(self):
        """Test that hard delete fails with wrong confirmation"""
        self.client.force_authenticate(user=self.user1)
        url = reverse('league-detail', kwargs={'pk': self.league1.pk}) + '?hard_delete=true'
        data = {'confirm_delete': 'Wrong Name'}
        response = self.client.delete(url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_hard_delete_with_championships(self):
        """Test that hard delete is blocked if league has championships"""
        # Create a championship
        Championship.objects.create(
            league=self.league1,
            name='Test Championship',
            start_date='2025-01-01'
        )

        self.client.force_authenticate(user=self.user1)
        url = reverse('league-detail', kwargs={'pk': self.league1.pk}) + '?hard_delete=true'
        data = {'confirm_delete': self.league1.name}
        response = self.client.delete(url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('championships', response.data['detail'].lower())

    def test_hard_delete_empty_league_success(self):
        """Test that hard delete succeeds for empty league with confirmation"""
        self.client.force_authenticate(user=self.user1)
        url = reverse('league-detail', kwargs={'pk': self.league1.pk}) + '?hard_delete=true'
        data = {'confirm_delete': self.league1.name}
        response = self.client.delete(url, data)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # League should be deleted
        self.assertFalse(League.objects.filter(pk=self.league1.pk).exists())

    def test_delete_as_non_admin_fails(self):
        """Test that non-admins cannot delete league"""
        self.client.force_authenticate(user=self.user2)
        url = reverse('league-detail', kwargs={'pk': self.league1.pk})
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


    # ===== ARCHIVE/RESTORE TESTS =====

    def test_archive_active_league(self):
        """Test archiving an active league"""
        self.client.force_authenticate(user=self.user1)
        url = reverse('league-archive', kwargs={'pk': self.league1.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_active'])

        # Verify in database
        league = League.objects.get(pk=self.league1.pk)
        self.assertFalse(league.is_active)

    def test_archive_already_archived_league(self):
        """Test that archiving an already archived league fails"""
        self.client.force_authenticate(user=self.inactive_league.creator)
        url = reverse('league-archive', kwargs={'pk': self.inactive_league.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already archived', response.data['detail'].lower())

    def test_restore_archived_league(self):
        """Test restoring an archived league"""
        self.client.force_authenticate(user=self.user1)
        url = reverse('league-restore', kwargs={'pk': self.inactive_league.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_active'])

        # Verify in database
        league = League.objects.get(pk=self.inactive_league.pk)
        self.assertTrue(league.is_active)

    def test_restore_active_league_fails(self):
        """Test that restoring an already active league fails"""
        self.client.force_authenticate(user=self.user1)
        url = reverse('league-restore', kwargs={'pk': self.league1.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already active', response.data['detail'].lower())

    def test_archive_as_non_admin_fails(self):
        """Test that non-admins cannot archive league"""
        self.client.force_authenticate(user=self.user2)
        url = reverse('league-archive', kwargs={'pk': self.league1.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_restore_as_non_admin_fails(self):
        """Test that non-admins cannot restore league"""
        LeagueMembership.objects.create(
            league=self.inactive_league,
            user=self.user2,
            role=LeagueMemberRole.MEMBER
        )

        self.client.force_authenticate(user=self.user2)
        url = reverse('league-restore', kwargs={'pk': self.inactive_league.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ===== ARCHIVED LEAGUE VISIBILITY TESTS =====

    def test_list_shows_archived_leagues_to_members(self):
        """Test that members can see their archived leagues"""
        self.client.force_authenticate(user=self.user1)
        url = reverse('league-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should see: ACC League, LMU League, Old League (archived, member), Private Club
        league_names = [league['name'] for league in response.data["results"]]
        self.assertIn('Old League', league_names)

    def test_list_hides_archived_leagues_from_non_members(self):
        """Test that non-members cannot see archived leagues"""
        self.client.force_authenticate(user=self.user3)
        url = reverse('league-list')
        response = self.client.get(url)
        league_names = [league['name'] for league in response.data["results"]]
        self.assertNotIn('Old League', league_names)

    def test_can_view_archived_league_details_as_member(self):
        """Test that members can view details of archived leagues"""
        self.client.force_authenticate(user=self.user1)
        url = reverse('league-detail', kwargs={'pk': self.inactive_league.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Old League')
        self.assertFalse(response.data['is_active'])

    def test_filter_by_is_active(self):
        """Test filtering leagues by is_active status"""
        self.client.force_authenticate(user=self.user1)

        # Filter active only
        url = reverse('league-list')
        response = self.client.get(url, {'is_active': 'true'})
        league_names = [l['name'] for l in response.data["results"]]
        self.assertNotIn('Old League', league_names)

        # Filter inactive only
        response = self.client.get(url, {'is_active': 'false'})
        league_names = [l['name'] for l in response.data["results"]]
        self.assertIn('Old League', league_names)
        self.assertNotIn('ACC League', league_names)

    # ===== JOIN TESTS =====

    def test_join_public_league(self):
        """Test joining a public league"""
        self.client.force_authenticate(user=self.user3)
        url = reverse('league-join', kwargs={'pk': self.league1.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            LeagueMembership.objects.filter(
                league=self.league1,
                user=self.user3
            ).exists()
        )

    def test_join_league_already_member(self):
        """Test that users cannot join a league twice"""
        self.client.force_authenticate(user=self.user1)
        url = reverse('league-join', kwargs={'pk': self.league1.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already a member', response.data['detail'].lower())

    def test_join_invite_only_league_with_valid_code(self):
        """Test joining INVITE_ONLY league with valid code"""
        self.client.force_authenticate(user=self.user3)
        url = reverse('league-join', kwargs={'pk': self.invite_only_league.pk})
        data = {'invitation_code': self.invite_only_league.invitation_code}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_join_invite_only_league_with_invalid_code(self):
        """Test joining INVITE_ONLY league with invalid code"""
        self.client.force_authenticate(user=self.user3)
        url = reverse('league-join', kwargs={'pk': self.invite_only_league.pk})
        data = {'invitation_code': 'wrong_code'}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_join_invite_only_league_without_code(self):
        """Test joining INVITE_ONLY league without code"""
        self.client.force_authenticate(user=self.user3)
        url = reverse('league-join', kwargs={'pk': self.invite_only_league.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_join_league_unauthenticated(self):
        """Test that unauthenticated users cannot join"""
        url = reverse('league-join', kwargs={'pk': self.league1.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_cannot_join_archived_league(self):
        """Test that users cannot join archived leagues"""
        self.assertFalse(self.inactive_league.is_member(self.user3))

        self.client.force_authenticate(user=self.user3)
        url = reverse('league-join', kwargs={'pk': self.inactive_league.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


    # ===== LEAVE TESTS =====

    def test_leave_league_as_member(self):
        """Test leaving a league as regular member"""
        # Add user3 as member
        LeagueMembership.objects.create(
            league=self.league1,
            user=self.user3,
            role=LeagueMemberRole.MEMBER
        )

        self.client.force_authenticate(user=self.user3)
        url = reverse('league-leave', kwargs={'pk': self.league1.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            LeagueMembership.objects.filter(
                league=self.league1,
                user=self.user3
            ).exists()
        )

    def test_leave_league_as_admin(self):
        """Test that admins cannot leave their own league"""
        self.client.force_authenticate(user=self.user1)
        url = reverse('league-leave', kwargs={'pk': self.league1.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('admin cannot leave', response.data['detail'].lower())

    def test_leave_league_not_member(self):
        """Test leaving a league you're not part of"""
        self.client.force_authenticate(user=self.user3)
        url = reverse('league-leave', kwargs={'pk': self.league1.pk})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ===== KICK TESTS =====

    def test_kick_member_as_admin(self):
        """Test kicking a member as admin"""
        # Add user3 as member
        LeagueMembership.objects.create(
            league=self.league1,
            user=self.user3,
            role=LeagueMemberRole.MEMBER
        )

        self.client.force_authenticate(user=self.user1)
        url = reverse('league-kick', kwargs={'pk': self.league1.pk})
        data = {'user_id': self.user3.id}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            LeagueMembership.objects.filter(
                league=self.league1,
                user=self.user3
            ).exists()
        )

    def test_kick_admin(self):
        """Test that admins cannot be kicked"""
        self.client.force_authenticate(user=self.user2)
        url = reverse('league-kick', kwargs={'pk': self.league1.pk})
        data = {'user_id': self.user1.id}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_kick_member_as_non_admin(self):
        """Test that non-admins cannot kick members"""
        LeagueMembership.objects.create(
            league=self.league1,
            user=self.user3,
            role=LeagueMemberRole.MEMBER
        )

        self.client.force_authenticate(user=self.user3)
        url = reverse('league-kick', kwargs={'pk': self.league1.pk})
        data = {'user_id': self.user3.id}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_kick_without_user_id(self):
        """Test kicking without providing user_id"""
        self.client.force_authenticate(user=self.user1)
        url = reverse('league-kick', kwargs={'pk': self.league1.pk})
        response = self.client.post(url, {})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_kick_nonexistent_member(self):
        """Test kicking a user who is not a member"""
        self.client.force_authenticate(user=self.user1)
        url = reverse('league-kick', kwargs={'pk': self.league1.pk})
        data = {'user_id': self.user3.id}  # user3 is not a member
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ===== PROMOTE/DEMOTE TESTS =====

    def test_admin_cannot_demote_another_admin(self):
        """Test that admin cannot demote another admin"""
        # Create second admin
        LeagueMembership.objects.create(
            league=self.league1,
            user=self.user2,
            role=LeagueMemberRole.ADMIN
        )

        self.client.force_authenticate(user=self.user1)
        url = reverse('league-promote', kwargs={'pk': self.league1.pk})
        data = {'user_id': self.user2.id, 'new_role': LeagueMemberRole.MODERATOR}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('cannot change role of another admin', response.data['detail'].lower())

    def test_admin_can_demote_themselves_if_not_last_admin(self):
        """Test that admin can demote themselves if there's another admin"""
        # Create second admin
        LeagueMembership.objects.create(
            league=self.league1,
            user=self.user2,
            role=LeagueMemberRole.ADMIN
        )

        self.client.force_authenticate(user=self.user1)
        url = reverse('league-promote', kwargs={'pk': self.league1.pk})
        data = {'user_id': self.user1.id, 'new_role': LeagueMemberRole.MODERATOR}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify demotion
        membership = LeagueMembership.objects.get(league=self.league1, user=self.user1)
        self.assertEqual(membership.role, LeagueMemberRole.MODERATOR)

    def test_last_admin_cannot_demote_themselves(self):
        """Test that the only admin cannot demote themselves"""
        self.client.force_authenticate(user=self.user1)
        url = reverse('league-promote', kwargs={'pk': self.league1.pk})
        data = {'user_id': self.user1.id, 'new_role': LeagueMemberRole.MODERATOR}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('only admin', response.data['detail'].lower())

    def test_admin_can_promote_member_to_admin(self):
        """Test that admin can promote regular member to admin"""
        # Add user2 as member
        LeagueMembership.objects.create(
            league=self.league1,
            user=self.user2,
            role=LeagueMemberRole.MEMBER
        )

        self.client.force_authenticate(user=self.user1)
        url = reverse('league-promote', kwargs={'pk': self.league1.pk})
        data = {'user_id': self.user2.id, 'new_role': LeagueMemberRole.ADMIN}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify promotion
        membership = LeagueMembership.objects.get(league=self.league1, user=self.user2)
        self.assertEqual(membership.role, LeagueMemberRole.ADMIN)

    def test_admin_can_demote_moderator(self):
        """Test that admin can demote moderator to member"""
        # Add user2 as moderator
        LeagueMembership.objects.create(
            league=self.league1,
            user=self.user2,
            role=LeagueMemberRole.MODERATOR
        )

        self.client.force_authenticate(user=self.user1)
        url = reverse('league-promote', kwargs={'pk': self.league1.pk})
        data = {'user_id': self.user2.id, 'new_role': LeagueMemberRole.MEMBER}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify demotion
        membership = LeagueMembership.objects.get(league=self.league1, user=self.user2)
        self.assertEqual(membership.role, LeagueMemberRole.MEMBER)

    def test_promote_to_same_role_returns_error(self):
        """Test that promoting to same role returns error"""
        # Add user2 as moderator
        LeagueMembership.objects.create(
            league=self.league1,
            user=self.user2,
            role=LeagueMemberRole.MODERATOR
        )

        self.client.force_authenticate(user=self.user1)
        url = reverse('league-promote', kwargs={'pk': self.league1.pk})
        data = {'user_id': self.user2.id, 'new_role': LeagueMemberRole.MODERATOR}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already has role', response.data['detail'].lower())

    def test_moderator_cannot_promote(self):
        """Test that moderators cannot promote members"""
        # Add user2 as moderator
        LeagueMembership.objects.create(
            league=self.league1,
            user=self.user2,
            role=LeagueMemberRole.MODERATOR
        )
        # Add user3 as member
        LeagueMembership.objects.create(
            league=self.league1,
            user=self.user3,
            role=LeagueMemberRole.MEMBER
        )

        self.client.force_authenticate(user=self.user2)
        url = reverse('league-promote', kwargs={'pk': self.league1.pk})
        data = {'user_id': self.user3.id, 'new_role': LeagueMemberRole.MODERATOR}
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_promote_with_invalid_role(self):
        """Test that promoting with invalid role fails"""
        LeagueMembership.objects.create(
            league=self.league1,
            user=self.user2,
            role=LeagueMemberRole.MEMBER
        )

        self.client.force_authenticate(user=self.user1)
        url = reverse('league-promote', kwargs={'pk': self.league1.pk})
        data = {'user_id': self.user2.id, 'new_role': 'SUPER_ADMIN'}  # Invalid role
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ===== MEMBERS LIST TESTS =====

    def test_list_league_members(self):
        """Test listing all members of a league"""
        # Add some members
        LeagueMembership.objects.create(
            league=self.league1,
            user=self.user2,
            role=LeagueMemberRole.MODERATOR
        )
        LeagueMembership.objects.create(
            league=self.league1,
            user=self.user3,
            role=LeagueMemberRole.MEMBER
        )

        url = reverse('league-members', kwargs={'pk': self.league1.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 3)  # admin, moderator, member

        # Check order: admin first
        self.assertEqual(response.data[0]['role'], LeagueMemberRole.ADMIN)

    def test_list_members_empty_league(self):
        """Test listing members of a league with only admin"""
        url = reverse('league-members', kwargs={'pk': self.league2.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
