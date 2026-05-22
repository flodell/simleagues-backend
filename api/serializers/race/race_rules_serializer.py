from rest_framework import serializers

from core.models import RaceRules, RaceRulesTemplate


class RaceRulesTemplateSerializer(serializers.ModelSerializer):
    created_by = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = RaceRulesTemplate
        fields = [
            'id',
            'name',
            'created_by',
            'fuel_usage',
            'tire_wear',
            'tire_warmers',
            'mechanical_failures',
            'flag_rules',
            'track_limits',
            'track_limits_points',
            'is_dynamic',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_by', 'is_active', 'created_at', 'updated_at']

    def validate_name(self, value):
        user = self.context['request'].user
        qs = RaceRulesTemplate.objects.filter(created_by=user, name=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('You already have a template with this name.')
        return value


class RaceRulesSerializer(serializers.ModelSerializer):
    race = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = RaceRules
        fields = [
            'id',
            'race',
            'fuel_usage',
            'tire_wear',
            'tire_warmers',
            'mechanical_failures',
            'flag_rules',
            'track_limits',
            'track_limits_points',
            'is_dynamic',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'race', 'created_at', 'updated_at']

    def validate(self, attrs):
        # Re-validate the cross-field invariant: cannot set is_dynamic=False while >1 stages exist.
        # Only relevant when is_dynamic is being toggled to False on an existing instance.
        if self.instance and attrs.get('is_dynamic') is False:
            stage_count = self.instance.weather_stages.count()
            if stage_count > 1:
                raise serializers.ValidationError({
                    'is_dynamic': (
                        f'Cannot disable dynamic weather while {stage_count} weather stages exist. '
                        'Remove extra stages first.'
                    ),
                })
        return attrs

class ApplyTemplateSerializer(serializers.Serializer):
    """Input for POST /race-rules-templates/{id}/apply/."""
    race_id = serializers.IntegerField()
