from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from api.serializers.race.race_rules_template_serializer import RaceRulesTemplateSerializer
from core.models import RaceRulesTemplate
from core.permissions import IsTemplateOwnerOrReadOnly


class RaceRulesTemplateViewSet(viewsets.ModelViewSet):
    """CRUD for race rules templates. Users only see and manage their own templates."""

    serializer_class = RaceRulesTemplateSerializer
    permission_classes = [IsTemplateOwnerOrReadOnly]

    def get_queryset(self):
        qs = RaceRulesTemplate.objects.filter(created_by=self.request.user)
        if self.request.query_params.get('include_archived') != 'true':
            qs = qs.filter(is_active=True)
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        template = self.get_object()
        if request.query_params.get('hard') == 'true':
            template.delete()
        else:
            template.is_active = False
            template.save(update_fields=['is_active', 'updated_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Create a copy of this template under the current user with name '<name> (copy)'."""
        source = self.get_object()

        # Build a unique copy name to avoid colliding with the unique_together constraint.
        base_name = f'{source.name} (copy)'
        new_name = base_name
        counter = 2
        while RaceRulesTemplate.objects.filter(created_by=request.user, name=new_name).exists():
            new_name = f'{base_name} {counter}'
            counter += 1

        copy = RaceRulesTemplate.objects.create(
            name=new_name,
            created_by=request.user,
            fuel_usage=source.fuel_usage,
            tire_wear=source.tire_wear,
            tire_warmers=source.tire_warmers,
            mechanical_failures=source.mechanical_failures,
            flag_rules=source.flag_rules,
            track_limits=source.track_limits,
            track_limits_points=source.track_limits_points,
            is_dynamic=source.is_dynamic,
        )
        serializer = self.get_serializer(copy)
        return Response(serializer.data, status=status.HTTP_201_CREATED)