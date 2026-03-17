from django.db import transaction
from rest_framework import serializers

from core.models import Team
from core.models.choices import TeamRole
from core.models.team import TeamMembership


class TeamListSerializer(serializers.ModelSerializer):

    member_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Team
        fields = [
            'id',
            'name',
            'logo',
            'description',
            'member_count',
            'is_active',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']

class TeamDetailSerializer(serializers.ModelSerializer):
    member_count = serializers.IntegerField(read_only=True)  # From queryset annotation

    class Meta:
        model = Team
        fields = [
            'id',
            'name',
            'logo',
            'description',
            'member_count',
            'is_active',
            'total_races',
            'total_wins',
            'total_podiums',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'member_count',
            'total_races',
            'total_wins',
            'total_podiums',
            'created_at',
            'updated_at',
            ]

class TeamCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Team
        fields = ["name", "description", "logo"]

    def validate_name(self, value):
        if len(value) < 3:
            raise serializers.ValidationError("Name must be at least 3 characters long")
        return value.strip()

    @transaction.atomic
    def create(self, validated_data):
        user = self.context["request"].user

        team = Team.objects.create(**validated_data)
        TeamMembership.objects.create(team=team, user=user, role=TeamRole.OWNER)

        return team


class TeamUpdateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Team
        fields = ["name", "description", "logo"]

        def validate_name(self, value):
            """Ensure name is at least 3 characters."""
            if len(value.strip()) < 3:
                raise serializers.ValidationError(
                    "Team name must be at least 3 characters long."
                )
            return value.strip()