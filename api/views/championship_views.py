from django.db.models import Count, Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.mixins import LeaguePermissionMixin
from api.serializers.championship_serializers import (
    ChampionshipListSerializer,
    ChampionshipDetailSerializer,
    ChampionshipCreateSerializer,
    TeamSerializer,
    TeamCreateSerializer,
    DriverSerializer,
    DriverCreateSerializer,
    StandingSerializer,
)
from core.models import Team
from core.models.championship import Championship, Driver
from core.models.choices import ChampionshipStatus, ParticipantType, LeagueVisibility
from core.models.league import League


class ChampionshipViewSet(LeaguePermissionMixin, viewsets.ModelViewSet):
    """
    ViewSet for Championship CRUD operations and related actions.

    Provides endpoints for:
    - List/retrieve/create/update/delete championships
    - Manage teams within a championship
    - Manage drivers/participants
    - View standings
    """

    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ["league", "status", "participant_type", "season"]
    search_fields = ["name", "season"]
    ordering_fields = ["start_date", "created_at", "name"]
    ordering = ["-start_date"]

    # Action groups for permission management
    AUTH_ONLY_ACTIONS = frozenset(["register", "unregister", "remove_team"])
    STAFF_ACTIONS = frozenset(["update", "partial_update", "add_team", "add_driver"])
    ADMIN_ACTIONS = frozenset(["destroy", "update_status"])
    # Note: 'create' is handled manually in create() method due to lack of existing object

    def get_queryset(self):
        """Filter queryset based on user authentication and league membership"""
        user = self.request.user
        queryset = Championship.objects.select_related("league").annotate(
            participant_count=Count("participants", distinct=True),
            race_count=Count("races", distinct=True),
        )

        if not user.is_authenticated:
            # Public users can only see championships from public leagues
            return queryset.filter(
                league__visibility=LeagueVisibility.PUBLIC, league__is_active=True
            )

        # Authenticated users can see championships from:
        # - Public leagues
        # - Leagues they are members of
        return queryset.filter(
            Q(league__visibility=LeagueVisibility.PUBLIC, league__is_active=True)
            | Q(league__members=user)
        ).distinct()

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        serializer_map = {
            "create": ChampionshipCreateSerializer,
            "retrieve": ChampionshipDetailSerializer,
            "add_team": TeamCreateSerializer,
            "add_driver": DriverCreateSerializer,
            "register": DriverCreateSerializer,
        }
        return serializer_map.get(self.action, ChampionshipListSerializer)

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        """
        Create a championship. Only league admins can create championships.

        Permission check is done manually here because there's no object
        to check against in has_object_permission.
        """
        league_id = request.data.get("league")
        if not league_id:
            return Response(
                {"detail": "League is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            league = League.objects.get(pk=league_id)
            if not league.is_admin(request.user):
                return Response(
                    {"detail": "Only league admins can create championships."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        except League.DoesNotExist:
            return Response(
                {"detail": "League doesn't exist."},
                status=status.HTTP_404_NOT_FOUND,
            )

        return super().create(request, *args, **kwargs)

    @action(detail=True, methods=["get"])
    def teams(self, request, pk=None):
        """
        List all teams in this championship.

        Response 200: List of teams
        """
        championship = self.get_object()

        if championship.participant_type != ParticipantType.TEAM:
            return Response(
                {"detail": "This operation is only valid for team championships."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        teams = championship.teams.select_related("car")
        serializer = TeamSerializer(teams, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def add_team(self, request, pk=None):
        """
        Add a new team to the championship.

        Request body:
        {
            "name": "Team Name",
            "racing_number": 42,
            "car": 1,
            "owner": 1  // optional, defaults to current user
        }

        Response 201: Team created
        """
        championship = self.get_object()

        if championship.participant_type != ParticipantType.TEAM:
            return Response(
                {"detail": "This operation is only valid for team championships."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = self.get_serializer(
            data={**request.data, "championship": championship.id}
        )
        serializer.is_valid(raise_exception=True)
        team = serializer.save()

        return Response(TeamSerializer(team).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def remove_team(self, request, pk=None):
        """
        Remove a team from the championship.

        Staff can remove any team. Team owners can remove their own team.

        Request body:
        {
            "team_id": 1
        }

        Response 204: Team removed
        Response 403: Not authorized
        Response 404: Team not found
        """
        championship = self.get_object()
        team_id = request.data.get("team_id")

        if not team_id:
            return Response(
                {"detail": "team_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            team = championship.teams.get(id=team_id)
        except Team.DoesNotExist:
            return Response(
                {"detail": "Team not found in this championship."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check authorization: staff OR team owner
        is_staff = championship.league.is_staff(request.user)
        is_owner = team.owner == request.user

        if not is_staff and not is_owner:
            return Response(
                {"detail": "You are not authorized to remove this team."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check if championship is active
        if championship.status == ChampionshipStatus.ACTIVE:
            return Response(
                {"detail": "Cannot remove team from an active championship."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        team_name = team.name
        team.delete()

        return Response(
            {"detail": f'Team "{team_name}" successfully removed.'},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"])
    def drivers(self, request, pk=None):
        """
        List all drivers/participants in this championship.

        Response 200: List of drivers
        """
        championship = self.get_object()
        drivers = championship.participants.select_related("user", "team", "car")
        serializer = DriverSerializer(drivers, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def add_driver(self, request, pk=None):
        """
        Add a driver to the championship (staff action).

        Request body:
        {
            "user": 1,
            "car": 1,
            "racing_number": 42,
            "team": 1,  // optional, required for team championships
            "role": "Pro"  // optional
        }

        Response 201: Driver added
        """
        championship = self.get_object()

        # Check max participants
        if championship.max_participants:
            if championship.participants.count() >= championship.max_participants:
                return Response(
                    {"detail": "Maximum participants reached."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer = self.get_serializer(
            data={**request.data, "championship": championship.id}
        )
        serializer.is_valid(raise_exception=True)
        driver = serializer.save()

        return Response(DriverSerializer(driver).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def register(self, request, pk=None):
        """
        Register the current user as a driver in this championship.

        Request body:
        {
            "car": 1,
            "racing_number": 42,
            "team": 1,  // optional, required for team championships
            "role": "Pro"  // optional
        }

        Response 201: Successfully registered
        Response 400: Already registered or invalid data
        """
        championship = self.get_object()
        user = request.user

        # Check if already registered
        if championship.participants.filter(user=user).exists():
            return Response(
                {"detail": "You are already registered in this championship."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check championship status
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

        # Check max participants
        if championship.max_participants:
            if championship.participants.count() >= championship.max_participants:
                return Response(
                    {"detail": "Maximum participants reached."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # For team championships, team is required
        if championship.participant_type == ParticipantType.TEAM:
            if not request.data.get("team"):
                return Response(
                    {"detail": "Team is required for team championships."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer = self.get_serializer(
            data={
                **request.data,
                "championship": championship.id,
                "user": user.id,
            }
        )
        serializer.is_valid(raise_exception=True)
        driver = serializer.save()

        return Response(DriverSerializer(driver).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def unregister(self, request, pk=None):
        """
        Unregister the current user from this championship.

        Response 204: Successfully unregistered
        Response 404: Not registered
        """
        championship = self.get_object()
        user = request.user

        try:
            driver = championship.participants.get(user=user)

            # Check if championship has started
            if championship.status == ChampionshipStatus.ACTIVE:
                return Response(
                    {"detail": "Cannot unregister from an active championship."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            driver.delete()
            return Response(
                {"detail": "Successfully unregistered from the championship."},
                status=status.HTTP_204_NO_CONTENT,
            )

        except Driver.DoesNotExist:
            return Response(
                {"detail": "You are not registered in this championship."},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=True, methods=["get"])
    def standings(self, request, pk=None):
        """
        Get championship standings.

        Response 200: List of standings ordered by position
        """
        championship = self.get_object()
        standings = championship.standings.select_related(
            "driver__user", "team"
        ).order_by("position")
        serializer = StandingSerializer(standings, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def update_status(self, request, pk=None):
        """
        Update championship status.

        Request body:
        {
            "status": "ACTIVE"  // UPCOMING, ACTIVE, COMPLETED, CANCELLED
        }

        Response 200: Status updated
        """
        championship = self.get_object()
        new_status = request.data.get("status")

        if not new_status:
            return Response(
                {"detail": "status is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            status_value = ChampionshipStatus(new_status)
        except ValueError:
            return Response(
                {
                    "detail": f"Invalid status. Must be one of: {[s.value for s in ChampionshipStatus]}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        championship.status = status_value
        championship.save()

        return Response(
            {
                "detail": f"Championship status updated to {status_value.label}.",
                "status": status_value.value,
            },
            status=status.HTTP_200_OK,
        )
