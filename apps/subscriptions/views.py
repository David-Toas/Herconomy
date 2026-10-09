from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse
from apps.subscriptions.models import Subscription
from apps.subscriptions.serializers import (
    SubscriptionSerializer,
    SubscriptionCreateSerializer,
)
from apps.subscriptions.services import (
    create_subscription_with_payment,
    cancel_subscription,
)
from apps.common.permissions import IsCustomer

class SubscriptionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for listing, retrieving, creating, and cancelling subscriptions.
    Optimized with select_related to prevent N+1 queries.
    """
    serializer_class = SubscriptionSerializer
    filterset_fields = ['status']
    ordering_fields = ['created_at', 'end_date']

    def get_permissions(self):
        if self.action == 'create':
            permission_classes = [permissions.IsAuthenticated, IsCustomer]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return Subscription.objects.none()

        user = self.request.user
        if not user.is_authenticated:
            return Subscription.objects.none()

        # High performance query: join customer and plan hierarchy in a single SQL query
        base_qs = Subscription.objects.select_related(
            'customer',
            'plan',
            'plan__provider'
        )

        if user.role == 'ADMIN' or user.is_staff:
            return base_qs

        if user.is_provider:
            # Providers can view subscriptions to their plans
            return base_qs.filter(plan__provider=user)

        # Customers can only view their own subscriptions
        return base_qs.filter(customer=user)

    @extend_schema(
        summary="Subscribe to a plan",
        description="Creates a subscription in PENDING status and generates a simulated payment reference.",
        request=SubscriptionCreateSerializer,
        responses={
            201: OpenApiResponse(description="Subscription initiated in PENDING state"),
            400: OpenApiResponse(description="Validation error / Inactive plan"),
            409: OpenApiResponse(description="Active or pending subscription already exists"),
        }
    )
    def create(self, request, *args, **kwargs):
        serializer = SubscriptionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        plan_id = serializer.validated_data['plan_id']
        result = create_subscription_with_payment(
            customer=request.user,
            plan_id=plan_id
        )

        return Response(result, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Cancel a subscription",
        description="Sets the subscription status to CANCELLED.",
        request=None,
        responses={
            200: SubscriptionSerializer,
            403: OpenApiResponse(description="Permission denied"),
        }
    )
    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        subscription = self.get_object()
        cancelled_sub = cancel_subscription(subscription=subscription, user=request.user)
        return Response(
            SubscriptionSerializer(cancelled_sub).data,
            status=status.HTTP_200_OK
        )
