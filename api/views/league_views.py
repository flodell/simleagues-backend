from django.db.models import Count, Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK

from api.permissions import IsLeagueAdmin, IsLeagueStaff
from api.serializers.league_serializers import LeagueCreateSerializer, LeagueDetailSerializer, LeagueListSerializer, \
    LeagueMembershipSerializer
from core.models.choices import LeagueVisibility, LeagueMemberRole
from core.models.league import League, LeagueMembership



class LeagueViewSet(viewsets.ModelViewSet):
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['visibility', 'is_active', 'game']
    search_fields = ['name', 'game__name']
    ordering_fields = ['created_at', 'name', 'member_count']
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        queryset = League.objects.select_related('game').annotate(
            member_count=Count('members', distinct=True),
            championship_count=Count('championships', distinct=True)
        )
        if not user.is_authenticated:
            return queryset.filter(visibility=LeagueVisibility.PUBLIC ,is_active=True)
        return queryset.filter(Q(visibility=LeagueVisibility.PUBLIC) | Q(members=user))

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'create':
            return LeagueCreateSerializer
        elif self.action == 'retrieve':
            return LeagueDetailSerializer
        return LeagueListSerializer

    def get_permissions(self):
        """Set permissions based on action"""
        if self.action == 'create':
            permission_classes = [IsAuthenticated]
        elif self.action in ['update', 'partial_update']:
            permission_classes = [IsAuthenticated, IsLeagueStaff]
        elif self.action == 'destroy':
            permission_classes = [IsAuthenticated, IsLeagueAdmin]
        elif self.action in ['join', 'leave']:
            permission_classes = [IsAuthenticated]
        elif self.action in ['kick', 'promote']:
            permission_classes = [IsAuthenticated, IsLeagueStaff]
        else:
            permission_classes = [AllowAny]

        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        """
        Create league and automatically add creator as owner/admin.
        """
        league = serializer.save()
        LeagueMembership.objects.create(
            league=league,
            user=self.request.user,
            role=LeagueMemberRole.ADMIN,
            is_admin=True
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def join(self, request):
        """
        Join a league. Requires invite_code for private leagues.

        Request body (for private leagues):
        {
            "invite_code": "abc123xyz"
        }

        Response 201:
        {
            "id": 1,
            "user": 5,
            "username": "john_doe",
            "email": "john@example.com",
            "role": "member",
            "is_admin": false,
            "joined_at": "2024-01-15T10:30:00Z"
        }
        """
        league = self.get_object()
        user = request.user

        # Check if already a member
        if LeagueMembership.objects.filter(league=league, user=user).exists():
            return Response(
                {'detail': 'You are already a member of this league.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check visibility and invite code for private leagues
        if league.visibility == LeagueVisibility.PRIVATE:
            invite_code = request.data.get('invite_code')
            if not invite_code or invite_code != league.invite_code:
                return Response(
                    {'detail': 'Invalid or missing invite code.'},
                    status=status.HTTP_403_FORBIDDEN
                )

        # Create membership
        membership = LeagueMembership.objects.create(
            league=league,
            user=user,
            role=LeagueMemberRole.MEMBER,
        )

        serializer = LeagueMembershipSerializer(membership)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def leave(self, request, pk=None):
        """
        Leave a league. Admin cannot leave their own league.

        Response 204: Successfully left
        Response 400: Owner tried to leave
        Response 404: Not a member
        """
        league = self.get_object()
        user = request.user

        try:
            membership = LeagueMembership.objects.get(league=league, user=user)

            if membership.role == LeagueMemberRole.ADMIN:
                return Response(
                    {'detail': 'Admin cannot leave. Transfer ownership or delete the league.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            membership.delete()
            return Response(
                {'detail': 'Successfully left the league.'},
                status=status.HTTP_204_NO_CONTENT
            )

        except LeagueMembership.DoesNotExist:
            return Response(
                {'detail': 'You are not a member of this league.'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsLeagueAdmin])
    def kick(self, request, pk=None):
        """
        Kick a member from the league. Moderator cannot kick admin.

        Request body:
        {
            "user_id": 123
        }

        Response 204: Successfully removed
        Response 400: Tried to kick owner or missing user_id
        Response 404: Member not found
        """
        league = self.get_object()
        user_id = request.data.get('user_id')

        if not user_id:
            return Response(
                {'detail': 'user_id is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            membership = LeagueMembership.objects.get(league=league, user_id=user_id)

            if membership.role == LeagueMemberRole.ADMIN:
                return Response(
                    {'detail': 'Cannot kick the league admin.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            membership.delete()
            return Response(
                {'detail': 'Member successfully removed.'},
                status=status.HTTP_204_NO_CONTENT
            )

        except LeagueMembership.DoesNotExist:
            return Response(
                {'detail': 'Member not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsLeagueAdmin])
    def promote(self, request):
        pass

    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        """
        List all members of the league with their roles.
        Ordered by: admins first, then by role, then by join date.

        Response 200: List of memberships
        """
        league = self.get_object()
        memberships = league.memberships.select_related('user').order_by(
            '-is_admin', 'role', 'joined_at'
        )
        serializer = LeagueMembershipSerializer(memberships, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def championships(self, request, pk=None):
        """
        List all championships in this league.

        Response 200: List of championships
        """
        league = self.get_object()
        championships = league.championships.all()

        #serializer = ChampionshipListSerializer(championships, many=True)
        return Response(HTTP_200_OK)