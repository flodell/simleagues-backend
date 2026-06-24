from rest_framework import generics
from rest_framework.generics import get_object_or_404

from api.serializers.race.race_rules_serializer import RaceRulesSerializer
from core.models import Race, RaceRules
from core.permissions import IsRaceManagerOrReadOnly
from core.services.race_permissions import can_view_race


class RaceRulesView(generics.RetrieveUpdateAPIView):
    """
    GET    /races/{race_pk}/rules/  — fetch the rules for this race
    PUT    /races/{race_pk}/rules/  — full update
    PATCH  /races/{race_pk}/rules/  — partial update
    """

    serializer_class = RaceRulesSerializer
    permission_classes = [IsRaceManagerOrReadOnly]

    def get_object(self):
        race = get_object_or_404(Race, pk=self.kwargs['race_pk'])
        # Visibility check at read level (mirrors RaceViewSet.get_queryset).
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            if not can_view_race(self.request.user, race):
                from django.http import Http404
                raise Http404('Race not found.')
        rules = get_object_or_404(RaceRules, race=race)
        self.check_object_permissions(self.request, rules)
        return rules

