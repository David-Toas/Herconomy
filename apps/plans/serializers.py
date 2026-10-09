from rest_framework import serializers
from apps.plans.models import Plan, BillingInterval

class PlanSerializer(serializers.ModelSerializer):
    provider_email = serializers.EmailField(source='provider.email', read_only=True)
    provider_id = serializers.IntegerField(source='provider.id', read_only=True)

    class Meta:
        model = Plan
        fields = (
            'id',
            'name',
            'description',
            'price',
            'billing_interval',
            'is_active',
            'provider_id',
            'provider_email',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('id', 'provider_id', 'provider_email', 'created_at', 'updated_at')

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than 0.")
        return value

    def create(self, validated_data):
        user = self.context['request'].user
        validated_data['provider'] = user
        return super().create(validated_data)
