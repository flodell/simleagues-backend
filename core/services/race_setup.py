from core.constants import DEFAULT_WEATHER
from core.models import RaceRules, RaceWeather


def ensure_race_rules_and_weather(race):
    """
    Idempotent: creates default RaceRules + 1 RaceWeather for a Race if missing.
    Call from RaceViewSet.perform_create() after saving the race.
    """
    if hasattr(race, 'rules'):
        return race.rules
    rules = RaceRules.objects.create(race=race)
    RaceWeather.objects.create(rules=rules, order=1, **DEFAULT_WEATHER)
    return rules
