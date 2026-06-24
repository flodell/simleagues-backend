from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from api.serializers.race.race_rules_serializer import RaceRulesTemplateSerializer, ApplyTemplateSerializer, \
    RaceRulesSerializer
from core.constants import RACE_RULES_TEMPLATE_FIELDS
from core.models import RaceRulesTemplate, RaceRules, Race
from core.permissions import IsTemplateOwnerOrReadOnly
from core.services.race_permissions import can_manage_race


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
            template_name = template.name
            template.delete()
            return Response(
                {'detail': f"Template '{template_name}' has been permanently deleted."},
                status=status.HTTP_200_OK,
            )
        template.is_active = False
        template.save(update_fields=['is_active', 'updated_at'])
        return Response(
            {'detail': f"Template '{template.name}' has been archived."},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        """Create a copy of this template under the current user."""
        source = self.get_object()

        base_name = f'{source.name} (copy)'
        new_name = base_name
        counter = 2
        while RaceRulesTemplate.objects.filter(created_by=request.user, name=new_name).exists():
            new_name = f'{base_name} {counter}'
            counter += 1

        copy = RaceRulesTemplate.objects.create(
            name=new_name,
            created_by=request.user,
            **{field: getattr(source, field) for field in RACE_RULES_TEMPLATE_FIELDS },
        )
        return Response(self.get_serializer(copy).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def apply(self, request, pk=None):
        """
        POST /race-rules-templates/{id}/apply/
        Body: { "race_id": <int> }
        Snapshots the template's fields into the target race's RaceRules.
        Does NOT touch RaceWeather stages.
        """
        template = self.get_object()

        input_serializer = ApplyTemplateSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        race_id = input_serializer.validated_data['race_id']

        race = get_object_or_404(Race, pk=race_id)
        rules = get_object_or_404(RaceRules, race=race)

        if not can_manage_race(request.user, race):
            return Response(
                {'detail': 'You do not have permission to apply a template to this race.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Cross-modèle check: if template sets is_dynamic=False but race has >1 stage, refuse.
        if not template.is_dynamic and rules.weather_stages.count() > 1:
            return Response(
                {'detail': (
                    'Cannot apply a static template while the race has multiple weather stages. '
                    'Remove extra stages first.'
                )},
                status=status.HTTP_400_BAD_REQUEST,
            )

        for field in RACE_RULES_TEMPLATE_FIELDS :
            setattr(rules, field, getattr(template, field))
        rules.save()

        return Response(RaceRulesSerializer(rules).data, status=status.HTTP_200_OK)

