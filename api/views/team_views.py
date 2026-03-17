from django.db.models import Count, Q
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from api.serializers.team_serializers import TeamListSerializer, TeamCreateSerializer, TeamUpdateSerializer, \
    TeamDetailSerializer
from core.models import Team
from core.models.choices import TeamRole
from core.models.team import TeamMembership, TeamJoinRequest
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

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def join_request(self, request, pk=None):
        """Request to join a team."""
        team = self.get_object()

        if TeamMembership.objects.filter(team=team, user=request.user, is_active=True).exists():
            return Response(
                {"detail": "You are already a member of this team."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if TeamJoinRequest.objects.filter(team=team, user=request.user, status="pending").exists():
            return Response(
                {"detail": "You already have a pending request to join this team."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        TeamJoinRequest.objects.create(
            team=team,
            user=request.user,
            message=request.data.get("message", ""),
        )
        return Response(
            {"detail": "Join request sent."},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def cancel_request(self, request, pk=None):
        """Cancel your own pending join request."""
        team = self.get_object()

        join_request = TeamJoinRequest.objects.filter(
            team=team, user=request.user, status="pending"
        ).first()

        if not join_request:
            return Response(
                {"detail": "No pending request found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        join_request.status = "cancelled"
        join_request.save(update_fields=["status"])
        return Response(
            {"detail": "Join request cancelled."},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, IsTeamManager])
    def approve_request(self, request, pk=None):
        """Approve a pending join request. Owner or manager only."""
        team = self.get_object()

        join_request = TeamJoinRequest.objects.filter(
            team=team, pk=request.data.get("request_id"), status="pending"
        ).first()

        if not join_request:
            return Response(
                {"detail": "No pending request found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        join_request.accept(resolved_by=request.user)
        return Response(
            {"detail": f"{join_request.user.username} has been added to the team."},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, IsTeamManager])
    def reject_request(self, request, pk=None):
        """Reject a pending join request. Owner or manager only."""
        team = self.get_object()

        join_request = TeamJoinRequest.objects.filter(
            team=team, pk=request.data.get("request_id"), status="pending"
        ).first()

        if not join_request:
            return Response(
                {"detail": "No pending request found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        join_request.reject(resolved_by=request.user)
        return Response(
            {"detail": f"Request from {join_request.user.username} has been rejected."},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def leave(self, request, pk=None):
        """Leave a team. Owner must transfer ownership or delete the team first."""
        team = self.get_object()

        membership = TeamMembership.objects.filter(
            team=team, user=request.user, is_active=True
        ).first()

        if not membership:
            return Response(
                {"detail": "You are not a member of this team."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if membership.role == TeamRole.OWNER:
            return Response(
                {"detail": "You are the owner. Transfer ownership or delete the team before leaving."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership.delete()
        return Response(
            {"detail": f"You have left {team.name}."},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, IsTeamManager])
    def kick(self, request, pk=None):
        """Remove a member from the team. Owner or manager only.

        Managers cannot kick the owner or other managers.
        """
        team = self.get_object()
        user_id = request.data.get("user_id")

        membership = TeamMembership.objects.filter(
            team=team, user_id=user_id, is_active=True
        ).first()

        if not membership:
            return Response(
                {"detail": "Member not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if membership.role == TeamRole.OWNER:
            return Response(
                {"detail": "Cannot kick the team owner."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Managers cannot kick other managers
        requester_membership = TeamMembership.objects.get(team=team, user=request.user, is_active=True)
        if requester_membership.role == TeamRole.MANAGER and membership.role == TeamRole.MANAGER:
            return Response(
                {"detail": "Managers cannot kick other managers."},
                status=status.HTTP_403_FORBIDDEN,
            )

        username = membership.user.username
        membership.delete()
        return Response(
            {"detail": f"{username} has been removed from the team."},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, IsTeamManager])
    def set_role(self, request, pk=None):
        """Change a member's role. Owner or manager only.

        - Role 'owner' is forbidden (use transfer_ownership instead)
        - Managers can only assign 'driver' or 'reserve'
        - Managers cannot change the role of other managers
        """
        team = self.get_object()
        user_id = request.data.get("user_id")
        new_role = request.data.get("role")

        if new_role == TeamRole.OWNER:
            return Response(
                {"detail": "Use transfer_ownership to assign the owner role."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        membership = TeamMembership.objects.filter(
            team=team, user_id=user_id, is_active=True
        ).first()

        if not membership:
            return Response(
                {"detail": "Member not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if membership.role == TeamRole.OWNER:
            return Response(
                {"detail": "Cannot change the owner's role."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        requester_membership = TeamMembership.objects.get(team=team, user=request.user, is_active=True)
        if requester_membership.role == TeamRole.MANAGER:
            if membership.role == TeamRole.MANAGER:
                return Response(
                    {"detail": "Managers cannot change the role of other managers."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        membership.role = new_role
        membership.save(update_fields=["role"])
        return Response(
            {"detail": f"{membership.user.username}'s role has been updated to '{new_role}'."},
            status=status.HTTP_200_OK,
        )