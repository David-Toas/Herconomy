from rest_framework import serializers
from apps.payments.models import Payment

class PaymentWebhookSerializer(serializers.Serializer):
    event = serializers.CharField(required=True)
    reference = serializers.CharField(required=True)
    provider_reference = serializers.CharField(required=False, allow_blank=True, default='')
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=True)

class PaymentSerializer(serializers.ModelSerializer):
    subscription_id = serializers.IntegerField(source='subscription.id', read_only=True)

    class Meta:
        model = Payment
        fields = (
            'id',
            'reference',
            'subscription_id',
            'amount',
            'currency',
            'status',
            'provider_reference',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields
