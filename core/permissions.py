from rest_framework.permissions import BasePermission, SAFE_METHODS


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