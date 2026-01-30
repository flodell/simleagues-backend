from rest_framework import serializers

from core.models import LeagueMembership, Team
from core.models.championship import Championship, Driver, Standing
from core.models.choices import ParticipantType, LeagueMemberRole


# Driver


class DriverCreateSerializer(serializers.ModelSerializer):
    """Serializer for registering a driver in a championship"""

    class Meta:
        model = Driver
        fields = ["id", "championship", "user", "team", "car", "racing_number", "role"]
        read_only_fields = ["id"]


class DriverSerializer(serializers.ModelSerializer):
    """Serializer for drivers in a championship"""

    username = serializers.CharField(source="user.username", read_only=True)
    team_name = serializers.CharField(source="team.name", read_only=True)
    car_name = serializers.CharField(source="car.name", read_only=True)

    class Meta:
        model = Driver
        fields = [
            "id",
            "user",
            "username",
            "team",
            "team_name",
            "car",
            "car_name",
            "racing_number",
            "role",
            "joined_at",
        ]
        read_only_fields = ["joined_at"]


# Team


class TeamCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a team in a championship"""

    class Meta:
        model = "Team"
        fields = ["id", "championship", "owner", "name", "racing_number", "car"]
        read_only_fields = ["id"]

    def validate_name(self, value):
        """Validate team name"""
        if len(value) < 3:
            raise serializers.ValidationError(
                "Team name must be at least 3 characters long."
            )
        return value

    def validate(self, data):
        user = self.context["request"].user
        championship = data["championship"]
        owner = data.get("owner", user)
        data["owner"] = owner

        self._validate_league_membership(user, championship.league)
        self._validate_league_membership(owner, championship.league)

        # 2. Only staff can assign different owner
        if owner != user:
            self._validate_staff_permission(user, championship.league)

        # 3. Owner cannot already own another team in this championship
        self._validate_owner_uniqueness(owner, championship)

        # 4. Racing number must be unique in championship
        self._validate_racing_number_uniqueness(data["racing_number"], championship)

        return data

    def _validate_league_membership(self, user, league):
        """Validate that a user is a member of the league"""
        if not league.members.filter(id=user.id).exists():
            raise serializers.ValidationError(
                f"User {user.username} must be a member of the league."
            )

    def _validate_staff_permission(self, user, league):
        """Check if user has staff permission"""
        try:
            membership = LeagueMembership.objects.get(user=user, league=league)
            if membership.role not in [
                LeagueMemberRole.ADMIN,
                LeagueMemberRole.MODERATOR,
            ]:
                raise serializers.ValidationError(
                    "Only staff members can create teams for other users."
                )
        except LeagueMembership.DoesNotExist:
            raise serializers.ValidationError("User is not a member of the league.")

    def _validate_owner_uniqueness(self, owner, championship):
        """Ensure owner doesn't already own a team in this championship"""
        existing_team = Team.objects.filter(
            championship=championship, owner=owner
        ).first()

        if existing_team:
            raise serializers.ValidationError(
                f"You already own team '{existing_team.name}' in this championship. "
                f"An owner cannot have multiple teams in the same championship."
            )

    def _validate_racing_number_uniqueness(self, racing_number, championship):
        """Ensure racing number is unique in championship"""
        if Team.objects.filter(
            championship=championship, racing_number=racing_number
        ).exists():
            raise serializers.ValidationError(
                {
                    "racing_number": "This racing number is already taken in this championship."
                }
            )


class TeamSerializer(serializers.ModelSerializer):
    """Serializer for teams in a championship"""

    owner_username = serializers.CharField(source="owner.username", read_only=True)
    car_name = serializers.CharField(source="car.name", read_only=True)
    driver_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Team
        fields = [
            "id",
            "owner",
            "owner_username",
            "name",
            "racing_number",
            "car",
            "car_name",
            "driver_count",
            "created_at",
        ]
        read_only_fields = ["created_at"]


class StandingSerializer(serializers.ModelSerializer):
    """Serializer for championship standings"""

    driver_name = serializers.CharField(source="driver.user.username", read_only=True)
    team_name = serializers.CharField(source="team.name", read_only=True)

    class Meta:
        model = Standing
        fields = [
            "id",
            "position",
            "driver",
            "driver_name",
            "team",
            "team_name",
            "total_points",
            "races_completed",
            "wins",
            "podiums",
            "fastest_laps",
            "dnf_count",
            "dsq_count",
            "best_finish",
        ]


class ChampionshipListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for championship list"""

    league_name = serializers.CharField(source="league.name", read_only=True)
    participant_count = serializers.IntegerField(read_only=True)
    team_count = serializers.IntegerField(read_only=True)
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
            "team_count",
            "race_count",
            "created_at",
        ]


class ChampionshipDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single championship retrieval"""

    league_name = serializers.CharField(source="league.name", read_only=True)
    participant_count = serializers.IntegerField(read_only=True)
    team_count = serializers.IntegerField(read_only=True)
    race_count = serializers.IntegerField(read_only=True)
    teams = TeamSerializer(many=True, read_only=True)
    participants = DriverSerializer(many=True, read_only=True)
    standings = StandingSerializer(many=True, read_only=True)
    user_participation = serializers.SerializerMethodField()

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
            "team_count",
            "race_count",
            "teams",
            "participants",
            "standings",
            "user_participation",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def get_user_participation(self, obj):
        """Get current user's participation in this championship"""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None

        driver = obj.participants.filter(user=request.user).first()
        if driver:
            return DriverSerializer(driver).data
        return None


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
