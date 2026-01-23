from rest_framework.routers import DefaultRouter

from api.views.league_views import LeagueViewSet

router = DefaultRouter()
router.register(r'leagues', LeagueViewSet, basename='league')

urlpatterns = router.urls