from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from django.core.cache import cache
from drf_spectacular.utils import extend_schema, OpenApiParameter
from apps.plans.models import Plan
from apps.plans.serializers import PlanSerializer
from apps.common.permissions import IsProvider, IsPlanOwnerOrReadOnly
from apps.plans.services import (
    get_plans_cache_key,
    invalidate_plans_cache,
    PLANS_CACHE_TIMEOUT,
)

class PlanViewSet(viewsets.ModelViewSet):
    """
    CRUD ViewSet for subscription plans.
    - POST: Only providers can create plans.
    - GET: Public listing is cached in Redis with automatic cache invalidation on changes.
    - PATCH/DELETE: Only the owning provider can modify their plans.
    """
    serializer_class = PlanSerializer
    filterset_fields = ['billing_interval', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['price', 'created_at']

    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [permissions.IsAuthenticated, IsProvider]
        elif self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAuthenticated, IsPlanOwnerOrReadOnly]
        else:
            # Listing and retrieval are public
            permission_classes = [permissions.AllowAny]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        user = self.request.user
        qs = Plan.objects.select_related('provider')

        # If provider is viewing their own plans, show all (active and inactive)
        if self.request.query_params.get('my_plans') == 'true' and user.is_authenticated and user.is_provider:
            return qs.filter(provider=user)

        # Non-staff users viewing public plans should only see active plans
        if not (user.is_authenticated and (user.role == 'ADMIN' or user.is_staff)):
            qs = qs.filter(is_active=True)

        return qs

    @extend_schema(
        summary="List subscription plans",
        description="Returns paginated active subscription plans. Results are cached in Redis.",
        parameters=[
            OpenApiParameter(name="my_plans", type=bool, description="Filter to only plans owned by authenticated provider"),
        ]
    )
    def list(self, request, *args, **kwargs):
        # Only cache default public queries (not custom filtered or provider's own plans)
        is_custom_query = (
            request.query_params.get('my_plans') or
            request.query_params.get('search') or
            request.query_params.get('billing_interval')
        )
        page = request.query_params.get('page', '1')

        if not is_custom_query:
            cache_key = get_plans_cache_key(page=int(page) if page.isdigit() else 1)
            cached_data = cache.get(cache_key)
            if cached_data is not None:
                return Response(cached_data)

        # If not cached or custom query, perform DB query
        queryset = self.filter_queryset(self.get_queryset())
        page_obj = self.paginate_queryset(queryset)
        if page_obj is not None:
            serializer = self.get_serializer(page_obj, many=True)
            paginated_response = self.get_paginated_response(serializer.data)
            if not is_custom_query:
                cache.set(cache_key, paginated_response.data, timeout=PLANS_CACHE_TIMEOUT)
            return paginated_response

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        serializer.save()
        invalidate_plans_cache()

    def perform_update(self, serializer):
        serializer.save()
        invalidate_plans_cache()

    def perform_destroy(self, instance):
        instance.delete()
        invalidate_plans_cache()
