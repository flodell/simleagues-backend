from django.db.models import Count, Q
from rest_framework import viewsets, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from api.serializers.team_serializers import TeamListSerializer, TeamCreateSerializer, TeamUpdateSerializer, \
    TeamDetailSerializer
from core.models import Team
from core.permissions import IsTeamManager, IsTeamOwner


class TeamViewSet(viewsets.ModelViewSet):
    """
    ViewSet for Team CRUD operations.

    - List: All teams (public)
    - Create: Authenticated users
    - Retrieve: Anyone
    - Update: Owner or Manager
    - Delete: Owner only
    """

    def get_queryset(self):
        return Team.objects.annotate(
            member_counts=Count("memberships", filter=Q(memberships__is_active=True))
        ).order_by('-created_at')

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        serializer_map = {
            "create": TeamCreateSerializer,
            "update": TeamUpdateSerializer,
            "partial_update": TeamUpdateSerializer,
            "retrieve": TeamDetailSerializer,
        }
        return serializer_map.get(self.action, TeamListSerializer)

    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        elif self.action == 'create':
            return [IsAuthenticated()]
        elif self.action in ['update', 'partial_update']:
            return [IsAuthenticated(), IsTeamManager()]
        elif self.action == 'destroy':
            return [IsAuthenticated(), IsTeamOwner()]
        return [IsAuthenticated()]

    def destroy(self, request, *args, **kwargs):
        """
             Soft delete a team by default (archive it).

             Query params:
             - hard_delete=true : Permanently delete (requires confirmation)

             Only owner can delete their team.

             Examples:
             - DELETE /api/team/1/ → Archive (soft delete)
             - DELETE /api/team/1/?hard_delete=true → Permanent delete
             :param **kwargs:
             """
        team = self.get_object()
        hard_delete = request.query_params.get("hard_delete", "false").lower() == "true"

        if hard_delete:
            return self._hard_delete_team(team, request)
        else:
            return self._soft_delete_team(team)


    def _soft_delete_team(self, team):
        team.is_active = False
        team.save(update_fields=["is_active"])
        return Response(
            {"detail": f"Team '{team.name}' has been archived."},
            status=status.HTTP_200_OK,
        )

    def _hard_delete_team(self, team, request):
        team_name = team.name
        team.delete()
        return Response({"detail": f"Team '{team_name}' has been permanently deleted."},
            status=status.HTTP_200_OK,)
