from rest_framework import serializers

from core.models.championship import ChampionshipEntry


class ChampionshipEntrySerializer(serializers.ModelSerializer):

    user_username = serializers.CharField(source="user.username", read_only=True)
    team_name = serializers.CharField(source="team.name", read_only=True)
    car_name = serializers.CharField(source="car.name", read_only=True)

    class Meta:
        model = ChampionshipEntry
        fields = [
            "id",
            "championship",
            "user",
            "user_username",
            "team",
            "team_name",
            "car",
            "car_name",
            "racing_number",
            "status",
            "ban_reason",
            "joined_at",
            "updated_at",
        ]
        read_only_fields = ["id", "championship", "status", "ban_reason", "joined_at", "updated_at"]


class ChampionshipEntryCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = ChampionshipEntry
        fields = ["user", "team", "car", "racing_number"]

    def validate(self, data):
        championship = self.context.get("championship")
        errors = {}

        # Validate racing number uniqueness
        if ChampionshipEntry.objects.filter(
            championship=championship,
            racing_number=data.get("racing_number"),
        ).exists():
            errors["racing_number"] = "This racing number is already taken."

        # Validate team/user not already registered
        if data.get("team") and ChampionshipEntry.objects.filter(
            championship=championship, team=data["team"]
        ).exists():
            errors["team"] = "This team is already registered in this championship."

        if data.get("user") and ChampionshipEntry.objects.filter(
            championship=championship, user=data["user"], team__isnull=True
        ).exists():
            errors["user"] = "This user is already registered in this championship."

        if errors:
            raise serializers.ValidationError(errors)

        return data