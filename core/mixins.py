from rest_framework.permissions import IsAuthenticated, AllowAny

from core.permissions import IsLeagueStaff, IsLeagueAdmin


class LeaguePermissionMixin:

    AUTH_ONLY_ACTIONS: frozenset[str] = frozenset()
    STAFF_ACTIONS: frozenset[str] = frozenset()
    ADMIN_ACTIONS: frozenset[str] = frozenset()

    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in self.ADMIN_ACTIONS:
            perms = [IsAuthenticated, IsLeagueAdmin]
        elif self.action in self.STAFF_ACTIONS:
            perms = [IsAuthenticated, IsLeagueStaff]
        elif self.action in self.AUTH_ONLY_ACTIONS:
            perms = [IsAuthenticated]
            # Public
        else:
            perms = [AllowAny]
        return [p() for p in perms]
