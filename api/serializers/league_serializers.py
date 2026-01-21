from rest_framework import serializers

from core.models.league import LeagueMembership, League


class LeagueMembershipSerializer(serializers.ModelSerializer):
    """Serializer for league membership"""

    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = LeagueMembership
        fields = [
            'id', 'user', 'username', 'email',
            'role', 'joined_at'
        ]
        read_only_fields = ['joined_at']


class LeagueListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for league list"""

    member_count = serializers.IntegerField(read_only=True)
    championship_count = serializers.IntegerField(read_only=True)
    game_name = serializers.CharField(source='game.name', read_only=True)

    class Meta:
        model = League
        fields = [
            'id', 'name', 'description', 'visibility',
            'game', 'game_name', 'is_active',
            'member_count', 'championship_count',
            'created_at'
        ]


class LeagueDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single league retrieval"""

    member_count = serializers.IntegerField(read_only=True)
    championship_count = serializers.IntegerField(read_only=True)
    game_name = serializers.CharField(source='game.name', read_only=True)
    memberships = LeagueMembershipSerializer(many=True, read_only=True)

    # User's role in this league
    user_role = serializers.SerializerMethodField()

    class Meta:
        model = League
        fields = [
            'id', 'name', 'description', 'visibility',
            'invitation_code', 'game', 'game_name', 'is_active',
            'member_count', 'championship_count',
            'memberships', 'user_role',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['invitation_code', 'created_at', 'updated_at']

    def get_user_role(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None

        membership = obj.memberships.filter(user=request.user).first()
        return membership.role if membership else None

class LeagueCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = League
        fields = [
            'name', 'description', 'visibility', 'game'
        ]

    def validate_name(self, value):
        """Validate league name"""
        if len(value) < 3:
            raise serializers.ValidationError(
                "League name must be at least 3 characters long."
            )
        return value

    def validate_game(self, value):
        """Ensure game exists and is active (if you have is_active on Game)"""
        if not value:
            raise serializers.ValidationError("Game is required.")
        return value