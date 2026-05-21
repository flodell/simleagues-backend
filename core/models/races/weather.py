from django.core.exceptions import ValidationError
from django.db import models

from core.models.choices import SkyCondition


# TODO (multi-sim): sky_condition choices are currently LMU-specific.
# When adding a second simulator, move the valid options to Game (e.g. Game.sky_condition_options
# as JSONField) and drop the `choices=` constraint here.


class RaceWeather(models.Model):
    """A weather stageF within a race. 1 stage = static weather, up to 5 = dynamic."""

    MAX_STAGES = 5

    rules = models.ForeignKey(
        'core.RaceRules', on_delete=models.CASCADE, related_name='weather_stages'
    )
    order = models.PositiveSmallIntegerField()
    duration_minutes = models.PositiveIntegerField()
    sky_condition = models.CharField(
        max_length=15,
        choices=SkyCondition.choices,
        default=SkyCondition.CLEAR,
        help_text='LMU-specific values. Will move to Game.sky_condition_options for multi-sim support.',
    )
    ambient_temp = models.SmallIntegerField(help_text='Ambient temperature in °C')
    track_temp = models.SmallIntegerField(help_text='Track temperature in °C')
    rain_chance = models.PositiveSmallIntegerField(default=0, help_text='Rain probability 0-100%')

    class Meta:
        ordering = ['rules', 'order']
        constraints = [
            models.UniqueConstraint(
                fields=['rules', 'order'],
                name='unique_stage_order_per_rules',
            ),
            models.CheckConstraint(
                condition=models.Q(order__gte=1) & models.Q(order__lte=5),
                name='stage_order_between_1_and_5',
            ),
            models.CheckConstraint(
                condition=models.Q(rain_chance__lte=100),
                name='rain_chance_max_100',
            ),
        ]

    def __str__(self):
        return f'Stage {self.order} ({self.get_sky_condition_display()})'

    def clean(self):
        # Block adding a 2nd+ stage when rules are static.
        if not self.rules.is_dynamic:
            existing = self.rules.weather_stages.exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError(
                    'Cannot add multiple weather stages when is_dynamic=False on RaceRules.'
                )

        # Enforce max 5 stages.
        existing_count = self.rules.weather_stages.exclude(pk=self.pk).count()
        if existing_count >= self.MAX_STAGES:
            raise ValidationError(
                f'A race cannot have more than {self.MAX_STAGES} weather stages.'
            )