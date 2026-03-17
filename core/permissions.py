from rest_framework.permissions import BasePermission


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

    def has_object_permission(self, request, view, obj):
        # obj is a Team
        return obj.is_owner(request.user)


class IsTeamManager(BasePermission):
    """Team owner or manager can perform this action."""

    def has_object_permission(self, request, view, obj):
        # obj is a Team
        return obj.is_manager(request.user)