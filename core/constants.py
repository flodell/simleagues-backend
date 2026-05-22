from core.models.choices import SkyCondition

RACE_RULES_TEMPLATE_FIELDS = frozenset({
    'fuel_usage',
    'tire_wear',
    'tire_warmers',
    'mechanical_failures',
    'flag_rules',
    'track_limits',
    'track_limits_points',
    'is_dynamic',
})

# Default weather used when auto-creating a race's first stage.
DEFAULT_WEATHER = {
    'sky_condition': SkyCondition.CLEAR,
    'ambient_temp': 22,
    'track_temp': 28,
    'rain_chance': 0,
    'duration_minutes': 60,
}
