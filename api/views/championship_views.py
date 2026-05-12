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
    StandingSerializer,
)
from core.models import Team
from core.models.championship import Championship
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
    STAFF_ACTIONS = frozenset(["update", "partial_update"])
    ADMIN_ACTIONS = frozenset(["destroy", "update_status"])

    def get_queryset(self):
        """Filter queryset based on user authentication and league membership"""
        user = self.request.user
        queryset = Championship.objects.select_related("league").annotate(
            participant_count=Count("entries", distinct=True),
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
            "standings": StandingSerializer,
        }
        return serializer_map.get(self.action, ChampionshipListSerializer)

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated()]
        return super().get_permissions()

    def create(self, request, *args, **kwargs):
        """
        Create a championship. Only league admins can create championships.

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
    def standings(self, request, pk=None):
        """Get championship standings ordered by position."""
        championship = self.get_object()
        standings = championship.standings.select_related(
            "driver__user", "team"
        ).order_by("position")
        serializer = StandingSerializer(standings, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def update_status(self, request, pk=None):
        """Update championship status. Admin only."""
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
