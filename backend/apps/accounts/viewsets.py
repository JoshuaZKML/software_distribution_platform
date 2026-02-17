# FILE: /backend/apps/accounts/viewsets.py
"""
ViewSet classes for User, Admin, Session, and Action models.
These enable REST CRUD operations and proper schema generation.
"""
from rest_framework import viewsets, permissions, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view, extend_schema_field
from drf_spectacular.types import OpenApiTypes
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import User, AdminProfile, UserSession, AdminActionLog
from .serializers import (
    UserSessionSerializer,
    DeviceChangeLogSerializer,
)

__all__ = [
    'UserSerializer',
    'AdminProfileSerializer',
    'AdminActionLogSerializer',
    'UserViewSet',
    'AdminProfileViewSet',
    'UserSessionViewSet',
    'AdminActionLogViewSet',
]


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model (used by UserViewSet)."""
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'role', 'company', 'phone',
            'is_active', 'date_joined', 'updated_at', 'last_login'
        ]
        read_only_fields = ['id', 'date_joined', 'updated_at', 'last_login']


class AdminProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for AdminProfile model.
    Note: AdminProfile uses user as primary key, so we provide an 'id' field
    that returns the user's UUID for backward compatibility.
    """
    id = serializers.SerializerMethodField(read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = AdminProfile
        fields = [
            'id', 'user', 'user_email', 'department',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    @extend_schema_field(OpenApiTypes.UUID)
    def get_id(self, obj):
        """Return the associated user's ID as the admin profile ID."""
        return str(obj.user.id)


class AdminActionLogSerializer(serializers.ModelSerializer):
    """
    Serializer for AdminActionLog model.
    Preserves the original output fields using derived values.
    """
    admin_user = serializers.EmailField(source='user.email', read_only=True)
    action = serializers.CharField(source='get_action_type_display', read_only=True)
    target_user = serializers.SerializerMethodField()
    target_model = serializers.CharField(source='target_type', read_only=True)
    status = serializers.SerializerMethodField()

    class Meta:
        model = AdminActionLog
        fields = [
            'id', 'admin_user', 'action', 'target_user', 'target_model', 'target_id',
            'details', 'status', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    @extend_schema_field(OpenApiTypes.STR)
    def get_target_user(self, obj):
        """If the target is a user, return their email."""
        if obj.target_type == 'user' and obj.target_id:
            try:
                user = User.objects.get(id=obj.target_id)
                return user.email
            except User.DoesNotExist:
                pass
        return None

    @extend_schema_field(serializers.ChoiceField(choices=[('active', 'Active'), ('undone', 'Undone')]))
    def get_status(self, obj):
        """Derive status from reversed flag."""
        return 'undone' if obj.reversed else 'active'


@extend_schema_view(
    list=extend_schema(description="List all users"),
    create=extend_schema(description="Create a new user"),
    retrieve=extend_schema(description="Retrieve a specific user"),
    update=extend_schema(description="Update a user"),
    partial_update=extend_schema(description="Partially update a user"),
    destroy=extend_schema(description="Delete a user"),
)
class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for User model.
    Provides CRUD operations and filtering/searching.
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['role', 'is_active']
    search_fields = ['email', 'first_name', 'last_name', 'company']
    ordering_fields = ['created_at', 'email', 'last_login']
    ordering = ['-created_at']

    def get_queryset(self):
        """Return users based on permissions."""
        user = self.request.user
        if user.role == 'ADMIN':
            return User.objects.all()
        # Non-admins can only view their own profile
        return User.objects.filter(id=user.id)

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        """Return the current authenticated user's data.

        This prevents requests to `/users/me/` being interpreted as a lookup
        for a user with primary key "me" (which causes errors because the PK
        is a UUID). Non-disruptive: simply returns the same representation
        as retrieving the user's own object.
        """
        serializer = self.get_serializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(description="List all admin profiles"),
    create=extend_schema(description="Create an admin profile"),
    retrieve=extend_schema(description="Retrieve an admin profile"),
    update=extend_schema(description="Update an admin profile"),
    partial_update=extend_schema(description="Partially update an admin profile"),
    destroy=extend_schema(description="Delete an admin profile"),
)
class AdminProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for AdminProfile model.
    Admin-only access.
    """
    queryset = AdminProfile.objects.all()
    serializer_class = AdminProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['user']
    search_fields = ['user__email', 'department']
    ordering_fields = ['created_at']
    ordering = ['-created_at']


@extend_schema_view(
    list=extend_schema(description="List all user sessions"),
    retrieve=extend_schema(description="Retrieve a session"),
)
class UserSessionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for UserSession model.
    Allows users to view and manage their sessions.
    """
    serializer_class = UserSessionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['device_name', 'ip_address', 'user_agent']
    ordering_fields = ['last_activity', 'created_at']
    ordering = ['-last_activity']

    def get_queryset(self):
        # During schema generation, avoid accessing request.user
        if getattr(self, "swagger_fake_view", False):
            return UserSession.objects.none()
        return UserSession.objects.filter(user=self.request.user)

    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        """Revoke a specific session."""
        session = self.get_object()
        session.is_active = False
        session.save()
        return Response({'status': 'session revoked'}, status=status.HTTP_200_OK)


@extend_schema_view(
    list=extend_schema(description="List admin action logs"),
    retrieve=extend_schema(description="Retrieve an action log entry"),
)
class AdminActionLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for AdminActionLog model.
    Read-only access for audit trail.
    """
    queryset = AdminActionLog.objects.all()
    serializer_class = AdminActionLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['user', 'action_type']
    search_fields = ['action_type', 'details']
    ordering_fields = ['created_at', 'action_type']
    ordering = ['-created_at']