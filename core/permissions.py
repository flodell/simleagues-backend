from rest_framework import permissions
from rest_framework.permissions import BasePermission, SAFE_METHODS

from core.models.choices import LeagueMemberRole
from core.services.race_permissions import can_view_race, can_manage_race


# League
def get_league(obj):
    return getattr(obj, "league", obj)


class IsLeagueAdmin(BasePermission):
    def has_object_permission(self, request, view, obj):
        return get_league(obj).is_admin(request.user)


class IsLeagueStaff(BasePermission):
    def has_object_permission(self, request, view, obj):
        return get_league(obj).is_staff(request.user)


class IsLeagueMember(BasePermission):
    def has_object_permission(self, request, view, obj):
        return get_league(obj).is_member(request.user)


# Team


class IsTeamOwner(BasePermission):
    """Only team owner can perform this action."""

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        return obj.is_owner(request.user)


class IsTeamManager(BasePermission):
    """Team owner or manager can perform this action."""

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        return obj.is_manager(request.user)


# Rules template

class IsTemplateOwnerOrReadOnly(BasePermission):
    """Read access for authenticated users, write access only for the template's creator."""

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return obj.created_by_id == request.user.id

# Race Permissions

class IsRaceManagerOrReadOnly(permissions.BasePermission):
    """
    Read: anyone who can view the race (respects RaceVisibility + league membership).
    Write: creator or league staff (OWNER/ADMIN).
    """

    def has_permission(self, request, view):
        # Write actions require authentication; read is open (visibility check is per-object).
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        race = obj.race if hasattr(obj, 'race') else obj.rules.race
        if request.method in permissions.SAFE_METHODS:
            return can_view_race(request.user, race)
        return can_manage_race(request.user, race)

