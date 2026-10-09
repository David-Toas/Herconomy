from rest_framework import serializers
from apps.subscriptions.models import Subscription
from apps.plans.serializers import PlanSerializer

class SubscriptionCreateSerializer(serializers.Serializer):
    plan_id = serializers.IntegerField(required=True)

class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)
    customer_email = serializers.EmailField(source='customer.email', read_only=True)
    customer_id = serializers.IntegerField(source='customer.id', read_only=True)

    class Meta:
        model = Subscription
        fields = (
            'id',
            'customer_id',
            'customer_email',
            'plan',
            'status',
            'start_date',
            'end_date',
            'next_billing_date',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields
