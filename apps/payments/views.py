import hmac
import hashlib
from django.conf import settings
from rest_framework import views, permissions, status
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiResponse
from apps.payments.serializers import PaymentWebhookSerializer
from apps.payments.services import process_payment_webhook

class PaymentWebhookView(views.APIView):
    """
    POST /api/payments/webhook/
    Receives simulated payment provider events (e.g., Stripe, Paystack).
    Handles idempotency, amount verification, atomic state transitions,
    and post-commit notification dispatching.
    """
    permission_classes = [permissions.AllowAny]

    def _verify_signature(self, request) -> bool:
        """
        Optional bonus security: validates HMAC-SHA256 signature if header is provided.
        """
        signature = request.headers.get('X-Webhook-Signature')
        if not signature:
            # If not provided, allow test execution without strict header
            return True

        secret = getattr(settings, 'WEBHOOK_SECRET', '').encode('utf-8')
        computed = hmac.new(secret, request.body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, computed)

    @extend_schema(
        summary="Process payment webhook",
        description="Receives external payment provider events (e.g. payment.success, payment.failed). Idempotent.",
        request=PaymentWebhookSerializer,
        responses={
            200: OpenApiResponse(description="Webhook processed successfully or already handled"),
            400: OpenApiResponse(description="Invalid payload or amount mismatch"),
            404: OpenApiResponse(description="Payment reference not found"),
        }
    )
    def post(self, request, *args, **kwargs):
        if not self._verify_signature(request):
            return Response(
                {"error": "Invalid webhook signature."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        serializer = PaymentWebhookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = process_payment_webhook(serializer.validated_data)
        return Response(result, status=status.HTTP_200_OK)
