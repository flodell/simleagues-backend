from django.db.models import Count, Q
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from api.serializers.race.race_serializers import (
    RaceListSerializer,
    RaceDetailSerializer,
    RaceCreateSerializer,
    RaceUpdateSerializer,
)
from core.models.choices import RaceVisibility, RaceStatus
from core.models.race import Race


class RaceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Race CRUD operations.

    - List/retrieve: depends on race visibility
    - Create: any authenticated user
    - Update: creator or league staff
    - Delete: creator or league staff (soft by default, hard with ?hard=true)
    """

    OWNER_ACTIONS = frozenset({"destroy"})
    WRITE_ACTIONS = frozenset({"update", "partial_update", "update_status"})

    def get_queryset(self):
        user = self.request.user
        queryset = Race.objects.annotate(
            entry_count=Count("entries", distinct=True)
        ).select_related("league", "championship", "track", "creator").order_by("-scheduled_date")

        if not user.is_authenticated:
            return queryset.filter(
                visibility=RaceVisibility.PUBLIC,
                is_active=True,
            )

        # Authenticated: public races + races from leagues they're in + their own races
        return queryset.filter(
            Q(visibility=RaceVisibility.PUBLIC, is_active=True) |
            Q(league__members=user) |
            Q(creator=user)
        ).distinct()

    def get_serializer_class(self):
        serializer_map = {
            "create": RaceCreateSerializer,
            "update": RaceUpdateSerializer,
            "partial_update": RaceUpdateSerializer,
            "retrieve": RaceDetailSerializer,
        }
        return serializer_map.get(self.action, RaceListSerializer)

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]
        return [IsAuthenticated()]

    def _is_authorized(self, request, race):
        """Check if user is creator or league staff."""
        if race.creator == request.user:
            return True
        if race.league and race.league.is_staff(request.user):
            return True
        return False

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

    def update(self, request, *args, **kwargs):
        race = self.get_object()
        if not self._is_authorized(request, race):
            return Response(
                {"detail": "You are not authorized to update this race."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """
        Delete a race.

        - Soft delete by default (is_active=False)
        - Hard delete with ?hard=true
        """
        race = self.get_object()

        if not self._is_authorized(request, race):
            return Response(
                {"detail": "You are not authorized to delete this race."},
                status=status.HTTP_403_FORBIDDEN,
            )

        hard_delete = request.query_params.get("hard", "").lower() == "true"

        if hard_delete:
            race_name = race.name
            race.delete()
            return Response(
                {"detail": f"Race '{race_name}' has been permanently deleted."},
                status=status.HTTP_200_OK,
            )

        race.is_active = False
        race.save(update_fields=["is_active"])
        return Response(
            {"detail": f"Race '{race.name}' has been archived."},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def update_status(self, request, pk=None):
        """Update race status. Creator or league staff only."""
        race = self.get_object()

        if not self._is_authorized(request, race):
            return Response(
                {"detail": "You are not authorized to update this race status."},
                status=status.HTTP_403_FORBIDDEN,
            )

        new_status = request.data.get("status")
        if not new_status:
            return Response(
                {"detail": "status is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            status_value = RaceStatus(new_status)
        except ValueError:
            return Response(
                {"detail": f"Invalid status. Must be one of: {[s.value for s in RaceStatus]}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        race.status = status_value
        race.save(update_fields=["status"])
        return Response(
            {
                "detail": f"Race status updated to {status_value.label}.",
                "status": status_value.value,
            },
            status=status.HTTP_200_OK,
        )