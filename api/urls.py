from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_nested import routers as nested_routers

from api.views.auth_views import (
    RegisterView,
    LoginView,
    LogoutView,
    MeView,
    UpdateUserPasswordView,
)
from api.views.championship_entry_views import ChampionshipEntryViewSet
from api.views.league_views import LeagueViewSet
from api.views.championship_views import ChampionshipViewSet
from api.views.team_views import TeamViewSet

router = DefaultRouter()
router.register(r"leagues", LeagueViewSet, basename="league")
router.register(r"championships", ChampionshipViewSet, basename="championship")
router.register(r"teams", TeamViewSet, basename="team")

championship_router = nested_routers.NestedDefaultRouter(router, r"championships", lookup="championship")
championship_router.register(r"entries", ChampionshipEntryViewSet, basename="championship-entries")

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="refresh_token"),
    path("me/", MeView.as_view(), name="me"),
    path("update-password/", UpdateUserPasswordView.as_view(), name="update_password"),
] + router.urls + championship_router.urls
