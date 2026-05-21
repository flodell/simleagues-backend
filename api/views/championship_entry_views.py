from django.db.models import Q
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from api.serializers.championship_entry_serializers import (
    ChampionshipEntryCreateSerializer,
    ChampionshipEntrySerializer,
)
from core.models.championship import Championship, ChampionshipEntry
from core.models.choices import (
    ChampionshipEntryStatus,
    LeagueVisibility,
    ChampionshipStatus,
)
from core.models.team import TeamMembership
from core.models.choices import TeamRole


class ChampionshipEntryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for ChampionshipEntry management.

    Nested under championship: /championships/{championship_pk}/entries/

    - List/retrieve: public or league members
    - Create (register): members only, workflow depends on league visibility
        - PUBLIC: auto-approved
        - INVITE_ONLY: pending, staff approves
        - PRIVATE: staff only
    - approve/reject/ban: staff only
    - destroy: staff or entrant themselves
    """

    STAFF_ACTIONS = frozenset({"approve", "reject", "ban"})

    def get_championship(self):
        return Championship.objects.select_related("league").get(
            pk=self.kwargs["championship_pk"]
        )

    def get_queryset(self):
        championship = self.get_championship()
        return ChampionshipEntry.objects.filter(
            championship=championship
        ).select_related("user", "team", "car")

    def get_serializer_class(self):
        if self.action in ["create", "register"]:
            return ChampionshipEntryCreateSerializer
        return ChampionshipEntrySerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        """Staff only — directly creates an approved entry."""
        championship = self.get_championship()

        if not championship.league.is_staff(request.user):
            return Response(
                {"detail": "Only league staff can directly create entries."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = serializer.save(
            championship=championship,
            status=ChampionshipEntryStatus.APPROVED,
            resolved_by=request.user,
        )
        return Response(
            ChampionshipEntrySerializer(entry).data,
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, *args, **kwargs):
        """Staff or entrant themselves can delete an entry."""
        championship = self.get_championship()
        entry = self.get_object()
        is_staff = championship.league.is_staff(request.user)

        is_entrant = (
            entry.user == request.user
            or TeamMembership.objects.filter(
                team=entry.team,
                user=request.user,
                role__in=[TeamRole.OWNER, TeamRole.MANAGER],
                is_active=True,
            ).exists()
        )

        if not is_staff and not is_entrant:
            return Response(
                {"detail": "You are not authorized to remove this entry."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if championship.status == ChampionshipStatus.ACTIVE:
            return Response(
                {"detail": "Cannot remove an entry from an active championship."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        entry.delete()
        return Response(
            {"detail": "Entry removed successfully."},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="register")
    def register(self, request, championship_pk=None):
        """
        Register as a participant in this championship.

        - PUBLIC league: auto-approved
        - INVITE_ONLY league: pending, staff approves
        - PRIVATE league: blocked, staff only
        """
        championship = self.get_championship()
        league = championship.league

        # Block if championship is not open
        if championship.status not in [
            ChampionshipStatus.UPCOMING,
            ChampionshipStatus.ACTIVE,
        ]:
            return Response(
                {
                    "detail": "Cannot register for a completed or cancelled championship."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Block if league is private
        if league.visibility == LeagueVisibility.PRIVATE:
            return Response(
                {"detail": "This championship is private. Contact staff to register."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Must be league member
        if not league.is_member(request.user):
            return Response(
                {"detail": "You must be a member of the league to register."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check max participants
        if championship.max_participants:
            if (
                championship.entries.filter(
                    status=ChampionshipEntryStatus.APPROVED
                ).count()
                >= championship.max_participants
            ):
                return Response(
                    {"detail": "Maximum participants reached."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # For team championship: requester must be owner or manager of the team
        team_id = request.data.get("team")
        if team_id:
            is_team_manager = TeamMembership.objects.filter(
                team_id=team_id,
                user=request.user,
                role__in=[TeamRole.OWNER, TeamRole.MANAGER],
                is_active=True,
            ).exists()
            if not is_team_manager:
                return Response(
                    {
                        "detail": "You must be owner or manager of the team to register it."
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

        entry_status = (
            ChampionshipEntryStatus.APPROVED
            if league.visibility == LeagueVisibility.PUBLIC
            else ChampionshipEntryStatus.PENDING
        )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = serializer.save(
            championship=championship,
            status=entry_status,
        )

        return Response(
            ChampionshipEntrySerializer(entry).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def approve(self, request, championship_pk=None, pk=None):
        """Approve a pending entry. Staff only."""
        championship = self.get_championship()

        if not championship.league.is_staff(request.user):
            return Response(
                {"detail": "Only league staff can approve entries."},
                status=status.HTTP_403_FORBIDDEN,
            )

        entry = self.get_object()
        try:
            entry.accept(resolved_by=request.user)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"detail": "Entry approved."},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def reject(self, request, championship_pk=None, pk=None):
        """Reject a pending entry. Staff only."""
        championship = self.get_championship()

        if not championship.league.is_staff(request.user):
            return Response(
                {"detail": "Only league staff can reject entries."},
                status=status.HTTP_403_FORBIDDEN,
            )

        entry = self.get_object()
        try:
            entry.reject(resolved_by=request.user)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"detail": "Entry rejected."},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def ban(self, request, championship_pk=None, pk=None):
        """Ban an entry. Staff only."""
        championship = self.get_championship()

        if not championship.league.is_staff(request.user):
            return Response(
                {"detail": "Only league staff can ban entries."},
                status=status.HTTP_403_FORBIDDEN,
            )

        entry = self.get_object()
        entry.ban(reason=request.data.get("reason", ""))

        return Response(
            {"detail": "Entry banned."},
            status=status.HTTP_200_OK,
        )
