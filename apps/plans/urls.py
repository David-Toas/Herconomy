from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.plans.views import PlanViewSet

router = DefaultRouter()
router.register(r'', PlanViewSet, basename='plan')

urlpatterns = [
    path('', include(router.urls)),
]
