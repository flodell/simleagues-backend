from rest_framework import serializers

from core.models import RaceWeather


class RaceWeatherSerializer(serializers.ModelSerializer):
    rules = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = RaceWeather
        fields = [
            'id',
            'rules',
            'order',
            'duration_minutes',
            'sky_condition',
            'ambient_temp',
            'track_temp',
            'rain_chance',
        ]
        read_only_fields = ['id', 'rules', 'order']

    def create(self, validated_data):
        # Auto-assign order as the next sequential value.
        rules = self.context['rules']
        validated_data['rules'] = rules
        validated_data['order'] = rules.weather_stages.count() + 1

        # Cross-field check: can't add more stages when static, or beyond MAX_STAGES.
        if not rules.is_dynamic and rules.weather_stages.exists():
            raise serializers.ValidationError(
                'Cannot add multiple weather stages when is_dynamic=False on RaceRules.'
            )
        if rules.weather_stages.count() >= RaceWeather.MAX_STAGES:
            raise serializers.ValidationError(
                f'A race cannot have more than {RaceWeather.MAX_STAGES} weather stages.'
            )

        return RaceWeather.objects.create(**validated_data)
