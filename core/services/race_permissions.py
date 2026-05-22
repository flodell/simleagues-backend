
def resolve_race_league(race):
    """
    Resolve the league a race belongs to.
    Returns None for standalone races.
    """
    if race.league:
        return race.league
    if race.championship:
        return race.championship.league
    return None


def can_view_race(user, race):
    """
    Mirror of RaceViewSet.get_queryset visibility rules.
    Use for nested endpoints (rules, weather) that must respect the same access.
    """
    from core.models.choices import RaceVisibility

    # Public active races are visible to everyone (incl. anonymous).
    if race.visibility == RaceVisibility.PUBLIC and race.is_active:
        return True

    # Beyond that, must be authenticated.
    if not user.is_authenticated:
        return False

    # Creator always sees their own races.
    if race.creator_id == user.id:
        return True

    # League members can see all races of their league.
    league = resolve_race_league(race)
    if league and league.members.filter(pk=user.pk).exists():
        return True

    return False


def can_manage_race(user, race):
    """
    Mirror of RaceViewSet._is_authorized.
    Creator or league staff (OWNER/ADMIN) can manage a race.
    """
    if not user.is_authenticated:
        return False

    if race.creator_id == user.id:
        return True

    league = resolve_race_league(race)
    if league is None:
        return False  # Standalone race — only creator can manage.

    return league.is_staff(user)
