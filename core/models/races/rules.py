from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from core.models.choices import (
    FlagRules,
    FuelUsage,
    MechanicalFailures,
    TireWear,
    TrackLimits,
)


# TODO (multi-sim): RaceRules choices are currently LMU-specific.
# When adding a second simulator, move the valid options to Game (e.g. Game.fuel_usage_options
# as JSONField) and drop the `choices=` constraints here. Validation will then be dynamic
# against the race's Game instance.


class RaceRulesTemplate(models.Model):
    """Reusable preset of race rules. Globally scoped, owned by its creator."""

    name = models.CharField(max_length=100)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='race_rules_templates',
    )

    fuel_usage = models.CharField(
        max_length=10,
        choices=FuelUsage.choices,
        default=FuelUsage.X1,
        help_text='LMU-specific values. Will move to Game.fuel_usage_options for multi-sim support.',
    )
    tire_wear = models.CharField(
        max_length=10,
        choices=TireWear.choices,
        default=TireWear.X1,
        help_text='LMU-specific values. Will move to Game.tire_wear_options for multi-sim support.',
    )
    tire_warmers = models.BooleanField(default=True)
    mechanical_failures = models.CharField(
        max_length=15,
        choices=MechanicalFailures.choices,
        default=MechanicalFailures.NORMAL,
        help_text='LMU-specific values. Will move to Game.mechanical_failures_options for multi-sim support.',
    )
    flag_rules = models.CharField(
        max_length=10,
        choices=FlagRules.choices,
        default=FlagRules.FULL,
        help_text='LMU-specific values. Will move to Game.flag_rules_options for multi-sim support.',
    )
    track_limits = models.CharField(
        max_length=10,
        choices=TrackLimits.choices,
        default=TrackLimits.NORMAL,
        help_text='LMU-specific values. Will move to Game.track_limits_options for multi-sim support.',
    )
    track_limits_points = models.PositiveIntegerField(default=3)
    is_dynamic = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['created_by', 'name'],
                name='unique_template_name_per_user',
            ),
        ]

    def __str__(self):
        return self.name


class RaceRules(models.Model):
    """Rules attached to a single race. Snapshot from a template at creation, or set independently."""

    race = models.OneToOneField('core.Race', on_delete=models.CASCADE, related_name='rules')

    fuel_usage = models.CharField(
        max_length=10,
        choices=FuelUsage.choices,
        default=FuelUsage.X1,
        help_text='LMU-specific values. Will move to Game.fuel_usage_options for multi-sim support.',
    )
    tire_wear = models.CharField(
        max_length=10,
        choices=TireWear.choices,
        default=TireWear.X1,
        help_text='LMU-specific values. Will move to Game.tire_wear_options for multi-sim support.',
    )
    tire_warmers = models.BooleanField(default=True)
    mechanical_failures = models.CharField(
        max_length=15,
        choices=MechanicalFailures.choices,
        default=MechanicalFailures.NORMAL,
        help_text='LMU-specific values. Will move to Game.mechanical_failures_options for multi-sim support.',
    )
    flag_rules = models.CharField(
        max_length=10,
        choices=FlagRules.choices,
        default=FlagRules.FULL,
        help_text='LMU-specific values. Will move to Game.flag_rules_options for multi-sim support.',
    )
    track_limits = models.CharField(
        max_length=10,
        choices=TrackLimits.choices,
        default=TrackLimits.NORMAL,
        help_text='LMU-specific values. Will move to Game.track_limits_options for multi-sim support.',
    )
    track_limits_points = models.PositiveIntegerField(default=3)
    is_dynamic = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Rules for {self.race}'

    def clean(self):
        # Static weather: at most 1 stage. Block flipping is_dynamic=False if multiple stages exist.
        if not self.is_dynamic and self.pk:
            stage_count = self.weather_stages.count()
            if stage_count > 1:
                raise ValidationError({
                    'is_dynamic': (
                        f'Cannot disable dynamic weather while {stage_count} weather stages exist. '
                        'Remove extra stages first.'
                    ),
                })