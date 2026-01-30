from django.urls import path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from api.views.auth_views import (
    RegisterView,
    LoginView,
    LogoutView,
    MeView,
    UpdateUserPasswordView,
)
from api.views.league_views import LeagueViewSet
from api.views.championship_views import ChampionshipViewSet

router = DefaultRouter()
router.register(r"leagues", LeagueViewSet, basename="league")
router.register(r"championships", ChampionshipViewSet, basename="championship")

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="refresh_token"),
    path("me/", MeView.as_view(), name="me"),
    path("update-password/", UpdateUserPasswordView.as_view(), name="update_password"),
] + router.urls
