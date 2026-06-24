from django.db.models import F
from rest_framework import viewsets, status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response

from api.serializers.race.race_weather_serializer import RaceWeatherSerializer
from core.models import RaceWeather, RaceRules, Race
from core.permissions import IsRaceManagerOrReadOnly
from core.services.race_permissions import can_view_race, can_manage_race
from django.http import Http404


class RaceWeatherViewSet(viewsets.ModelViewSet):
    """
    Nested CRUD under /races/{race_pk}/weather/.
    `order` is auto-assigned on create (sequential), shifted on delete.
    """

    serializer_class = RaceWeatherSerializer
    permission_classes = [IsRaceManagerOrReadOnly]

    def get_race(self):
        race = get_object_or_404(Race, pk=self.kwargs['race_pk'])
        # Read visibility filter; write permissions handled by permission_classes per-object.
        if not can_view_race(self.request.user, race):
            raise Http404('Race not found.')
        return race

    def get_queryset(self):
        race = self.get_race()
        return RaceWeather.objects.filter(rules__race=race)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if self.action == 'create':
            race = self.get_race()
            context['rules'] = get_object_or_404(RaceRules, race=race)
        return context

    def create(self, request, *args, **kwargs):
        race = self.get_race()
        if not can_manage_race(request.user, race):
            return Response(
                {'detail': 'You do not have permission to add weather stages to this race.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().create(request, *args, **kwargs)

    def perform_destroy(self, instance):
        # A race always needs at least 1 weather stage.
        if instance.rules.weather_stages.count() <= 1:
            raise ValidationError('Cannot delete the only weather stage of a race.')

        deleted_order = instance.order
        rules = instance.rules
        instance.delete()
        # Renumber: shift down all stages with higher order to keep sequence 1...N.
        rules.weather_stages.filter(order__gt=deleted_order).update(order=F('order') - 1)
