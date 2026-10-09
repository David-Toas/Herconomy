from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema, OpenApiResponse
from apps.users.serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    UserSerializer,
)

class RegisterView(generics.CreateAPIView):
    """
    POST /api/auth/register/
    Registers a new Customer or Provider user account.
    """
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="Register a new user",
        description="Creates a new account (Customer or Provider) and returns JWT credentials.",
        responses={
            201: OpenApiResponse(description="User successfully registered"),
            400: OpenApiResponse(description="Validation error / duplicate email"),
        }
    )
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Generate tokens immediately upon registration
        refresh = RefreshToken.for_user(user)
        refresh['email'] = user.email
        refresh['role'] = user.role

        return Response(
            {
                'message': 'User registered successfully.',
                'user': UserSerializer(user).data,
                'tokens': {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                }
            },
            status=status.HTTP_201_CREATED
        )


class LoginView(generics.GenericAPIView):
    """
    POST /api/auth/login/
    Authenticates user credentials and issues JWT tokens.
    """
    serializer_class = UserLoginSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="User login",
        description="Authenticates via email and password, returning JWT access and refresh tokens.",
        responses={
            200: OpenApiResponse(description="Successful authentication"),
            400: OpenApiResponse(description="Invalid credentials"),
        }
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        return Response(
            {
                'message': 'Login successful.',
                'user': UserSerializer(data['user']).data,
                'tokens': {
                    'access': data['access'],
                    'refresh': data['refresh'],
                }
            },
            status=status.HTTP_200_OK
        )


class MeView(generics.RetrieveUpdateAPIView):
    """
    GET /api/auth/me/
    PATCH /api/auth/me/
    Retrieves or updates the authenticated user's profile.
    Role modifications are strictly forbidden.
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    @extend_schema(
        summary="Current user profile",
        description="Returns details for the currently authenticated user.",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Update current user profile",
        description="Updates user profile fields (name). The role field is read-only.",
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @extend_schema(exclude=True)
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)
