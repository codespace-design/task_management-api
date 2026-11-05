from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .auth_views import LogoutView
from .profile_views import (
    CandidateProfileAPIView,
    CandidateResumeAPIView,
    EmployerProfileAPIView,
)
from .tokens import EmailTokenObtainPairSerializer
from .views import RegisterView


class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer


urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/token/", EmailTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/logout/", LogoutView.as_view(), name="token_blacklist"),
    path(
        "profiles/candidate/",
        CandidateProfileAPIView.as_view(),
        name="candidate-profile",
    ),
    path(
        "profiles/candidate/<int:user_id>/",
        CandidateProfileAPIView.as_view(),
        name="candidate-profile-detail",
    ),
    path(
        "profiles/candidate/resume/",
        CandidateResumeAPIView.as_view(),
        name="candidate-resume",
    ),
    path(
        "profiles/candidate/<int:user_id>/resume/",
        CandidateResumeAPIView.as_view(),
        name="candidate-resume-detail",
    ),
    path(
        "profiles/employer/",
        EmployerProfileAPIView.as_view(),
        name="employer-profile",
    ),
    path(
        "profiles/employer/<int:user_id>/",
        EmployerProfileAPIView.as_view(),
        name="employer-profile-detail",
    ),
]
