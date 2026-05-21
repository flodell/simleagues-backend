from rest_framework import serializers

from core.models import RaceRulesTemplate


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
        # Enforce unique name per user (mirrors the DB constraint with a clean DRF error).
        user = self.context['request'].user
        qs = RaceRulesTemplate.objects.filter(created_by=user, name=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('You already have a template with this name.')
        return value