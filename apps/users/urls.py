from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from apps.users.views import RegisterView, LoginView, MeView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='auth-register'),
    path('login/', LoginView.as_view(), name='auth-login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('me/', MeView.as_view(), name='auth-me'),
]
