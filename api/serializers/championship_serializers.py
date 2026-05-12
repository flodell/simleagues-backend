from rest_framework import serializers

from core.models.championship import Championship, Standing
from core.models.choices import ParticipantType, LeagueMemberRole



class StandingSerializer(serializers.ModelSerializer):
    """Serializer for championship standings"""

    participant_name = serializers.SerializerMethodField()

    class Meta:
        model = Standing
        fields = [
            "id",
            "position",
            "participant",
            "participant_name",
            "team",
            "total_points",
            "races_completed",
            "wins",
            "podiums",
            "fastest_laps",
            "dnf_count",
            "dsq_count",
            "best_finish",
        ]

    def get_participant_name(self, obj):
        if obj.participant:
            if obj.participant.team:
                return obj.participant.team.name
            if obj.participant.user:
                return obj.participant.user.username
        return None

class ChampionshipListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for championship list"""

    league_name = serializers.CharField(source="league.name", read_only=True)
    participant_count = serializers.IntegerField(read_only=True)
    race_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Championship
        fields = [
            "id",
            "name",
            "season",
            "league",
            "league_name",
            "participant_type",
            "status",
            "start_date",
            "end_date",
            "participant_count",
            "race_count",
            "created_at",
        ]


class ChampionshipDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single championship retrieval"""

    league_name = serializers.CharField(source="league.name", read_only=True)
    participant_count = serializers.IntegerField(read_only=True)
    race_count = serializers.IntegerField(read_only=True)
    standings = StandingSerializer(many=True, read_only=True)

    class Meta:
        model = Championship
        fields = [
            "id",
            "name",
            "season",
            "description",
            "league",
            "league_name",
            "participant_type",
            "status",
            "start_date",
            "end_date",
            "min_drivers_per_team",
            "max_drivers_per_team",
            "point_system",
            "allowed_car_categories",
            "max_participants",
            "participant_count",
            "race_count",
            "standings",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class ChampionshipCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a championship"""

    class Meta:
        model = Championship
        fields = [
            "id",
            "name",
            "season",
            "description",
            "league",
            "participant_type",
            "start_date",
            "end_date",
            "min_drivers_per_team",
            "max_drivers_per_team",
            "point_system",
            "allowed_car_categories",
            "max_participants",
        ]
        read_only_fields = ["id"]

    def validate_name(self, value):
        """Validate championship name"""
        if len(value) < 3:
            raise serializers.ValidationError(
                "Championship name must be at least 3 characters long."
            )
        return value

    def validate(self, data):
        """Cross-field validation"""
        participant_type = data.get("participant_type")
        min_drivers = data.get("min_drivers_per_team")
        max_drivers = data.get("max_drivers_per_team")

        # Validate team driver limits
        if participant_type == ParticipantType.TEAM:
            if min_drivers and max_drivers and min_drivers > max_drivers:
                raise serializers.ValidationError(
                    {"min_drivers_per_team": "Minimum cannot be greater than maximum."}
                )

        # Validate dates
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError(
                {"end_date": "End date cannot be before start date."}
            )

        return data
