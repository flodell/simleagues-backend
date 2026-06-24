from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from api.serializers.race.race_lineup_serializers import (
    RaceLineupCreateSerializer,
    RaceLineupDriverCreateSerializer,
    RaceLineupDriverSerializer,
    RaceLineupSerializer,
)
from core.models import Race, RaceLineup, RaceLineupDriver, TeamMembership
from core.models.choices import TeamRole
from core.services.race_permissions import can_manage_race, can_view_race


# Roles within a team that can manage a lineup.
TEAM_MANAGER_ROLES = frozenset({TeamRole.OWNER, TeamRole.MANAGER})


class RaceLineupViewSet(viewsets.ModelViewSet):
    """
    ViewSet for RaceLineup management.

    Nested under race: /races/{race_pk}/lineups/

    - List/retrieve: anyone who can view the race
    - Create / destroy / add_driver / remove_driver: league staff or team owner/manager
    - Update: not supported (use add-driver/remove-driver actions instead)
    """

    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_race(self):
        race = get_object_or_404(Race, pk=self.kwargs["race_pk"])
        if not can_view_race(self.request.user, race):
            raise Http404("Race not found.")
        return race

    def get_queryset(self):
        race = self.get_race()
        return (
            RaceLineup.objects.filter(race=race)
            .select_related(
                "race_entry__team",
                "race_entry__championship_entry__team",
            )
            .prefetch_related("lineup_drivers__user")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return RaceLineupCreateSerializer
        return RaceLineupSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]
        return [IsAuthenticated()]

    def _can_manage_lineup(self, user, race, race_entry):
        """League staff (via can_manage_race) OR team owner/manager."""
        if can_manage_race(user, race):
            return True

        team = race_entry.team or (
            race_entry.championship_entry and race_entry.championship_entry.team
        )
        if not team:
            return False

        return TeamMembership.objects.filter(
            team=team,
            user=user,
            role__in=TEAM_MANAGER_ROLES,
            is_active=True,
        ).exists()

    def create(self, request, *args, **kwargs):
        """Create a lineup for a team race entry."""
        race = self.get_race()

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        race_entry = serializer.validated_data["race_entry"]

        if race_entry.race_id != race.pk:
            return Response(
                {"detail": "RaceEntry does not belong to this race."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not self._can_manage_lineup(request.user, race, race_entry):
            return Response(
                {"detail": "You are not authorized to manage this lineup."},
                status=status.HTTP_403_FORBIDDEN,
            )

        if RaceLineup.objects.filter(race=race, race_entry=race_entry).exists():
            return Response(
                {"detail": "A lineup already exists for this race entry."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        lineup = serializer.save(race=race)
        return Response(
            RaceLineupSerializer(lineup).data,
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, *args, **kwargs):
        """Delete a lineup."""
        race = self.get_race()
        lineup = self.get_object()

        if not self._can_manage_lineup(request.user, race, lineup.race_entry):
            return Response(
                {"detail": "You are not authorized to manage this lineup."},
                status=status.HTTP_403_FORBIDDEN,
            )

        lineup.delete()
        return Response(
            {"detail": "Lineup deleted."},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="add-driver")
    def add_driver(self, request, race_pk=None, pk=None):
        """Add a driver to the lineup."""
        race = self.get_race()
        lineup = self.get_object()

        if not self._can_manage_lineup(request.user, race, lineup.race_entry):
            return Response(
                {"detail": "You are not authorized to manage this lineup."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = RaceLineupDriverCreateSerializer(
            data=request.data,
            context={"lineup": lineup},
        )
        serializer.is_valid(raise_exception=True)
        driver = serializer.save(lineup=lineup)

        return Response(
            RaceLineupDriverSerializer(driver).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="remove-driver")
    def remove_driver(self, request, race_pk=None, pk=None):
        """Remove a driver from the lineup."""
        race = self.get_race()
        lineup = self.get_object()

        if not self._can_manage_lineup(request.user, race, lineup.race_entry):
            return Response(
                {"detail": "You are not authorized to manage this lineup."},
                status=status.HTTP_403_FORBIDDEN,
            )

        user_id = request.data.get("user_id")
        try:
            lineup_driver = lineup.lineup_drivers.get(user_id=user_id)
        except RaceLineupDriver.DoesNotExist:
            return Response(
                {"detail": "Driver not found in lineup."},
                status=status.HTTP_404_NOT_FOUND,
            )

        lineup_driver.delete()
        return Response(
            {"detail": "Driver removed from lineup."},
            status=status.HTTP_200_OK,
        )