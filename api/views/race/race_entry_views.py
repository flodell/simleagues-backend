from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from api.serializers.race.race_entry_serializers import (
    RaceEntryCreateSerializer,
    RaceEntrySerializer,
)
from core.models import RaceEntry
from core.models.races.race import Race
from core.models.championship import ChampionshipEntry
from core.models.choices import RaceEntryStatus, LeagueVisibility, RaceStatus, TeamRole
from core.models.team import TeamMembership


class RaceEntryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for RaceEntry management.

    Nested under race: /races/{race_pk}/entries/

    - List/retrieve: public
    - register: members only, workflow depends on league visibility
        - PUBLIC: auto-approved
        - INVITE_ONLY: pending, staff approves
        - PRIVATE: staff only
    - approve/reject/ban: staff only
    - destroy: staff or entrant themselves
    """

    def get_race(self):
        return Race.objects.select_related("league", "championship").get(
            pk=self.kwargs["race_pk"]
        )

    def get_queryset(self):
        race = self.get_race()
        return RaceEntry.objects.filter(race=race).select_related(
            "championship_entry__user",
            "championship_entry__team",
            "team",
            "user",
            "car",
        )

    def get_serializer_class(self):
        if self.action in ["create", "register"]:
            return RaceEntryCreateSerializer
        return RaceEntrySerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        """Staff only can directly create an approved entry."""
        race = self.get_race()

        if not race.league or not race.league.is_staff(request.user):
            return Response(
                {"detail": "Only league staff can directly create entries."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = serializer.save(
            race=race,
            status=RaceEntryStatus.APPROVED,
            resolved_by=request.user,
        )
        return Response(
            RaceEntrySerializer(entry).data,
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, *args, **kwargs):
        """Staff or entrant themselves can delete an entry."""
        race = self.get_race()
        entry = self.get_object()

        is_staff = race.league and race.league.is_staff(request.user)
        is_entrant = (
            entry.user == request.user
            or (
                entry.championship_entry
                and entry.championship_entry.user == request.user
            )
            or TeamMembership.objects.filter(
                team=entry.team
                or (entry.championship_entry and entry.championship_entry.team),
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

        if race.status == RaceStatus.IN_PROGRESS:
            return Response(
                {"detail": "Cannot remove an entry from an ongoing race."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        entry.delete()
        return Response(
            {"detail": "Entry removed successfully."},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], url_path="register")
    def register(self, request, race_pk=None):
        """
        Register as a participant in this race.

        - PUBLIC league: auto-approved
        - INVITE_ONLY league: pending, staff approves
        - PRIVATE league: blocked, staff only
        - No league (independent race): auto-approved
        """
        race = self.get_race()

        if race.status not in [RaceStatus.SCHEDULED]:
            return Response(
                {"detail": "Cannot register for a race that is not scheduled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Independent race — auto-approved, anyone can register
        if not race.league:
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            entry = serializer.save(race=race, status=RaceEntryStatus.APPROVED)
            return Response(
                RaceEntrySerializer(entry).data, status=status.HTTP_201_CREATED
            )

        league = race.league

        if league.visibility == LeagueVisibility.PRIVATE:
            return Response(
                {"detail": "This race is private. Contact staff to register."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not league.is_member(request.user):
            return Response(
                {"detail": "You must be a member of the league to register."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Championship race — must have an approved ChampionshipEntry
        if race.championship:
            championship_entry_id = request.data.get("championship_entry")
            if not championship_entry_id:
                return Response(
                    {
                        "detail": "championship_entry is required for championship races."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                championship_entry = ChampionshipEntry.objects.get(
                    pk=championship_entry_id,
                    championship=race.championship,
                    status=RaceEntryStatus.APPROVED,
                )
            except ChampionshipEntry.DoesNotExist:
                return Response(
                    {"detail": "No approved championship entry found."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check already registered
            if RaceEntry.objects.filter(
                race=race, championship_entry=championship_entry
            ).exists():
                return Response(
                    {"detail": "This entry is already registered for this race."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # For team entry: requester must be owner or manager
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
            RaceEntryStatus.APPROVED
            if league.visibility == LeagueVisibility.PUBLIC
            else RaceEntryStatus.PENDING
        )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = serializer.save(race=race, status=entry_status)

        return Response(
            RaceEntrySerializer(entry).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def approve(self, request, race_pk=None, pk=None):
        """Approve a pending entry. Staff only."""
        race = self.get_race()

        if not race.league or not race.league.is_staff(request.user):
            return Response(
                {"detail": "Only league staff can approve entries."},
                status=status.HTTP_403_FORBIDDEN,
            )

        entry = self.get_object()
        try:
            entry.accept(resolved_by=request.user)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": "Entry approved."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def reject(self, request, race_pk=None, pk=None):
        """Reject a pending entry. Staff only."""
        race = self.get_race()

        if not race.league or not race.league.is_staff(request.user):
            return Response(
                {"detail": "Only league staff can reject entries."},
                status=status.HTTP_403_FORBIDDEN,
            )

        entry = self.get_object()
        try:
            entry.reject(resolved_by=request.user)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": "Entry rejected."}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def ban(self, request, race_pk=None, pk=None):
        """Ban an entry. Staff only."""
        race = self.get_race()

        if not race.league or not race.league.is_staff(request.user):
            return Response(
                {"detail": "Only league staff can ban entries."},
                status=status.HTTP_403_FORBIDDEN,
            )

        entry = self.get_object()
        entry.ban(reason=request.data.get("reason", ""))
        return Response({"detail": "Entry banned."}, status=status.HTTP_200_OK)
