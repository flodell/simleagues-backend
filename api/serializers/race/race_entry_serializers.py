from rest_framework import serializers

from core.models.race import RaceEntry, RaceLineup


class RaceEntrySerializer(serializers.ModelSerializer):

    user_username = serializers.CharField(source="user.username", read_only=True)
    team_name = serializers.CharField(source="team.name", read_only=True)
    car_name = serializers.SerializerMethodField()
    racing_number_display = serializers.SerializerMethodField()

    class Meta:
        model = RaceEntry
        fields = [
            "id",
            "race",
            "championship_entry",
            "user",
            "user_username",
            "team",
            "team_name",
            "car",
            "car_name",
            "racing_number",
            "racing_number_display",
            "status",
            "ban_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "race",
            "status",
            "ban_reason",
            "created_at",
            "updated_at",
        ]

    def get_car_name(self, obj):
        if obj.championship_entry:
            return obj.championship_entry.car.name
        return obj.car.name if obj.car else None

    def get_racing_number_display(self, obj):
        if obj.championship_entry:
            return obj.championship_entry.racing_number
        return obj.racing_number


class RaceEntryCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = RaceEntry
        fields = ["championship_entry", "user", "team", "car", "racing_number"]

    def validate(self, data):
        race = self.context.get("race")
        errors = {}

        championship_entry = data.get("championship_entry")

        if championship_entry:
            # Championship context — car/racing_number/team/user not needed
            if (
                data.get("car")
                or data.get("racing_number")
                or data.get("team")
                or data.get("user")
            ):
                errors["championship_entry"] = (
                    "Cannot specify car, racing_number, team or user when championship_entry is set."
                )
        else:
            # Standalone context
            if data.get("team") and data.get("user"):
                errors["team"] = "Cannot have both team and user."
            if not data.get("team") and not data.get("user"):
                errors["team"] = (
                    "Must specify either team, user, or championship_entry."
                )
            if not data.get("car"):
                errors["car"] = "Car is required for standalone entries."
            if not data.get("racing_number"):
                errors["racing_number"] = (
                    "Racing number is required for standalone entries."
                )

            # Check racing number uniqueness
            if (
                data.get("racing_number")
                and RaceEntry.objects.filter(
                    race=race, racing_number=data["racing_number"]
                ).exists()
            ):
                errors["racing_number"] = "This racing number is already taken."

        if errors:
            raise serializers.ValidationError(errors)

        return data
