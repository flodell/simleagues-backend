from django.db.models import Count, Q, Case, When
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from api.serializers.championship_serializers import ChampionshipListSerializer
from core.mixins import LeaguePermissionMixin
from core.permissions import IsLeagueAdmin, IsLeagueStaff
from api.serializers.league_serializers import (
    LeagueCreateSerializer,
    LeagueDetailSerializer,
    LeagueListSerializer,
    LeagueMembershipSerializer,
)
from core.models.choices import LeagueVisibility, LeagueMemberRole
from core.models.league import League, LeagueMembership


class LeagueViewSet(LeaguePermissionMixin, viewsets.ModelViewSet):
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["visibility", "is_active", "game"]
    search_fields = ["name", "game__name"]
    ordering_fields = ["created_at", "name", "member_count"]
    ordering = ["-created_at"]

    AUTH_ONLY_ACTIONS = frozenset(["create", "join", "leave"])
    STAFF_ACTIONS = frozenset(["update", "partial_update", "kick"])
    ADMIN_ACTIONS = frozenset(["destroy", "archive", "restore", "promote"])

    def get_queryset(self):
        user = self.request.user
        queryset = League.objects.select_related("game").annotate(
            member_count=Count("members", distinct=True),
            championship_count=Count("championships", distinct=True),
        )
        if not user.is_authenticated:
            return queryset.filter(visibility=LeagueVisibility.PUBLIC, is_active=True)

        return queryset.filter(
            Q(visibility=LeagueVisibility.PUBLIC, is_active=True)
            | Q(visibility=LeagueVisibility.INVITE_ONLY, is_active=True)
            | Q(members=user)
        ).distinct()

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        serializer_map = {
            "create": LeagueCreateSerializer,
            "retrieve": LeagueDetailSerializer,
        }
        return serializer_map.get(self.action, LeagueListSerializer)

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated()]
        return super().get_permissions()

    def destroy(self, request, pk=None, **kwargs):
        """
        Soft delete a league by default (archive it).

        Query params:
        - hard_delete=true : Permanently delete (requires confirmation)

        Only admins can delete their league.

        Examples:
        - DELETE /api/leagues/1/ → Archive (soft delete)
        - DELETE /api/leagues/1/?hard_delete=true → Permanent delete
        :param **kwargs:
        """
        league = self.get_object()
        hard_delete = request.query_params.get("hard_delete", "false").lower() == "true"

        if hard_delete:
            return self._hard_delete_league(league, request)
        else:
            return self._soft_delete_league(league)

    def _soft_delete_league(self, league):
        """
        Archive the league (soft delete).

        Sets is_active=False. League remains in database and visible to members.
        """
        if not league.is_active:
            return Response(
                {"detail": "League is already archived."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        league.is_active = False
        league.save()

        return Response(
            {"detail": "League successfully archived.", "is_active": False},
            status=status.HTTP_200_OK,
        )

    def _hard_delete_league(self, league, request):
        """
        Permanently delete the league.

        Requires explicit confirmation and checks for existing data.

        Request body:
        {
            "confirm_delete": "League Name"
        }
        """
        confirm = request.data.get("confirm_delete")
        if confirm != league.name:
            return Response(
                {
                    "detail": f'To permanently delete, send "confirm_delete": "{league.name}"',
                    "required_confirmation": league.name,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Vérifier s'il y a du contenu important
        championship_count = league.championships.count()
        race_count = league.races.count()

        if championship_count > 0 or race_count > 0:
            return Response(
                {
                    "detail": "Cannot delete league with existing championships or races.",
                    "championships": championship_count,
                    "races": race_count,
                    "suggestion": "Archive the league instead or delete all content first.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Tout est OK, suppression définitive
        league_name = league.name
        league.delete()

        return Response(
            {"detail": f'League "{league_name}" permanently deleted.'},
            status=status.HTTP_204_NO_CONTENT,
        )

    @action(detail=True, methods=["post"])
    def join(self, request, pk=None):
        """
        Join a league. Requires invitation_code for private leagues.

        Request body (for private leagues):
        {
            "invitation_code": "abc123xyz"
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

        if not league.is_active:
            return Response(
                {
                    {
                        "detail": "Cannot join an archived league",
                        "status_code": status.HTTP_400_BAD_REQUEST,
                    }
                }
            )
        # Check if already a member
        if LeagueMembership.objects.filter(league=league, user=user).exists():
            return Response(
                {"detail": "You are already a member of this league."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check visibility and invite code for private leagues
        if league.visibility == LeagueVisibility.INVITE_ONLY:
            invitation_code = request.data.get("invitation_code")
            if not invitation_code or invitation_code != league.invitation_code:
                return Response(
                    {"detail": "Invalid or missing invite code."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Create membership
        membership = LeagueMembership.objects.create(
            league=league,
            user=user,
            role=LeagueMemberRole.MEMBER,
        )

        serializer = LeagueMembershipSerializer(membership)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
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
                    {
                        "detail": "Admin cannot leave. Transfer ownership or delete the league."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            membership.delete()
            return Response(
                {"detail": "Successfully left the league."},
                status=status.HTTP_204_NO_CONTENT,
            )

        except LeagueMembership.DoesNotExist:
            return Response(
                {"detail": "You are not a member of this league."},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=True, methods=["post"])
    def kick(self, request, pk=None):
        """
        Kick a member from the league. Moderator cannot kick admin.

        Request body:
        {
            "user_id": 123
        }

        Response 204: Successfully removed
        Response 400: Tried to kick admin or missing user_id
        Response 404: Member not found
        """
        league = self.get_object()
        user_id = request.data.get("user_id")

        if not user_id:
            return Response(
                {"detail": "user_id is required."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            membership = LeagueMembership.objects.get(league=league, user_id=user_id)

            if membership.role == LeagueMemberRole.ADMIN:
                return Response(
                    {"detail": "Cannot kick the league admin."},
                    status=status.HTTP_403_FORBIDDEN,
                )

            membership.delete()
            return Response(
                {"detail": "Member successfully removed."},
                status=status.HTTP_204_NO_CONTENT,
            )

        except LeagueMembership.DoesNotExist:
            return Response(
                {"detail": "Member not found."}, status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=["post"])
    def promote(self, request, pk=None):
        league = self.get_object()
        user_id = request.data.get("user_id")
        new_role = request.data.get("new_role")

        if not user_id or not new_role:
            return Response(
                {"detail": "user_id and new_role are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            role = LeagueMemberRole(new_role)
        except ValueError:
            return Response(
                {"detail": "Invalid new role."}, status=status.HTTP_400_BAD_REQUEST
            )

        try:
            membership = LeagueMembership.objects.get(league=league, user_id=user_id)
            current_role = membership.role

            if (
                current_role == LeagueMemberRole.ADMIN
                and membership.user != request.user
            ):
                return Response(
                    {
                        "detail": "Cannot change role of another admin. They must demote themselves."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            # Cannot demote yourself if you're the only admin
            if (
                membership.user == request.user
                and membership.role == LeagueMemberRole.ADMIN
            ):
                admin_count = league.memberships.filter(
                    role=LeagueMemberRole.ADMIN
                ).count()
                if admin_count == 1:
                    return Response(
                        {"detail": "Cannot change your role as the only admin."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # No change if same role
            if current_role == new_role:
                return Response(
                    {"detail": f"User already has role {new_role}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            membership.role = role
            membership.save()

            serializer = LeagueMembershipSerializer(membership)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except LeagueMembership.DoesNotExist:
            return Response(
                {"detail": "Member not found."}, status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=["get"])
    def members(self, request, pk=None):
        """
        List all members of the league with their roles.
        Ordered by: admins first, then by role, then by join date.

        Response 200: List of memberships
        """
        league = self.get_object()
        memberships = league.memberships.select_related("user").order_by(
            Case(
                When(role=LeagueMemberRole.ADMIN, then=0),
                When(role=LeagueMemberRole.MODERATOR, then=1),
                default=2,
            ),
            "joined_at",
        )
        serializer = LeagueMembershipSerializer(memberships, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def championships(self, request, pk=None):
        """
        List all championships in this league.

        Response 200: List of championships
        """
        league = self.get_object()
        championships = league.championships.all()

        serializer = ChampionshipListSerializer(championships, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        """
        Archive  a league.

        Only admins can perform this action.
        """
        league = self.get_object()

        if not league.is_active:
            return Response(
                {"detail": "League is already archived."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        league.is_active = False
        league.save()

        return Response(
            {"detail": f"League successfully archived", "is_active": False},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        """
        Restore  a league.

        Only admins can perform this action.
        """

        league = self.get_object()
        if league.is_active:
            return Response(
                {"detail": "League already active."}, status=status.HTTP_400_BAD_REQUEST
            )
        league.is_active = True
        league.save()
        return Response({"detail": f"League successfully restored", "is_active": True})
