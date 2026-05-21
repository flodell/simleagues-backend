from rest_framework import serializers

from core.models.race import Race


class RaceListSerializer(serializers.ModelSerializer):

    league_name = serializers.CharField(source="league.name", read_only=True)
    championship_name = serializers.CharField(source="championship.name", read_only=True)
    track_name = serializers.CharField(source="track.name", read_only=True)
    entry_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Race
        fields = [
            "id",
            "name",
            "league",
            "league_name",
            "championship",
            "championship_name",
            "track",
            "track_name",
            "round_number",
            "scheduled_date",
            "duration_minutes",
            "laps",
            "visibility",
            "status",
            "is_active",
            "entry_count",
            "created_at",
        ]


class RaceDetailSerializer(serializers.ModelSerializer):

    league_name = serializers.CharField(source="league.name", read_only=True)
    championship_name = serializers.CharField(source="championship.name", read_only=True)
    track_name = serializers.CharField(source="track.name", read_only=True)
    creator_username = serializers.CharField(source="creator.username", read_only=True)
    entry_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Race
        fields = [
            "id",
            "name",
            "league",
            "league_name",
            "championship",
            "championship_name",
            "track",
            "track_name",
            "creator",
            "creator_username",
            "round_number",
            "scheduled_date",
            "duration_minutes",
            "laps",
            "visibility",
            "invitation_code",
            "status",
            "is_active",
            "entry_count",
            "notes",
            "entered_by",
            "entered_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "creator", "invitation_code", "created_at", "updated_at"]


class RaceCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Race
        fields = [
            "id",
            "name",
            "league",
            "championship",
            "track",
            "round_number",
            "scheduled_date",
            "duration_minutes",
            "laps",
            "visibility",
            "notes",
        ]
        read_only_fields = ["id"]

    def validate(self, data):
        errors = {}

        if data.get("duration_minutes") and data.get("laps"):
            errors["duration_minutes"] = "Cannot set both duration and laps."

        if errors:
            raise serializers.ValidationError(errors)

        return data


class RaceUpdateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Race
        fields = [
            "name",
            "track",
            "scheduled_date",
            "duration_minutes",
            "laps",
            "visibility",
            "notes",
        ]