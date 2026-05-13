from rest_framework import serializers

from core.models import RaceLineupDriver, TeamMembership, RaceLineup


class RaceLineupDriverSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = RaceLineupDriver
        fields = ["id", "user", "username", "role"]


class RaceLineupSerializer(serializers.ModelSerializer):
    lineup_drivers = RaceLineupDriverSerializer(many=True, read_only=True)
    team_name = serializers.SerializerMethodField()

    class Meta:
        model = RaceLineup
        fields = [
            "id",
            "race",
            "race_entry",
            "team_name",
            "lineup_drivers",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "race", "created_at", "updated_at"]

    def get_team_name(self, obj):
        team = (
            obj.race_entry.team or
            (obj.race_entry.championship_entry and obj.race_entry.championship_entry.team)
        )
        return team.name if team else None


class RaceLineupCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = RaceLineup
        fields = ["race_entry"]

    def validate_race_entry(self, value):
        team = (
            value.team or
            (value.championship_entry and value.championship_entry.team)
        )
        if not team:
            raise serializers.ValidationError("RaceLineup can only be used for team race entries.")
        return value


class RaceLineupDriverCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = RaceLineupDriver
        fields = ["user", "role"]

    def validate_user(self, value):
        lineup = self.context.get("lineup")
        team = (
            lineup.race_entry.team or
            (lineup.race_entry.championship_entry and lineup.race_entry.championship_entry.team)
        )
        if not TeamMembership.objects.filter(team=team, user=value, is_active=True).exists():
            raise serializers.ValidationError(
                f"{value.username} is not an active member of {team.name}."
            )
        return value