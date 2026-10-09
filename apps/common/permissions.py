from rest_framework import permissions

class IsCustomer(permissions.BasePermission):
    """Allows access only to authenticated customers (or admins)."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.role == 'CUSTOMER' or request.user.role == 'ADMIN' or request.user.is_staff)
        )

class IsProvider(permissions.BasePermission):
    """Allows access only to authenticated service providers (or admins)."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.role == 'PROVIDER' or request.user.role == 'ADMIN' or request.user.is_staff)
        )

class IsAdminUserRole(permissions.BasePermission):
    """Allows access only to administrators."""
    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            (request.user.role == 'ADMIN' or request.user.is_staff or request.user.is_superuser)
        )

class IsPlanOwnerOrReadOnly(permissions.BasePermission):
    """
    Object-level permission to allow anyone to read,
    but only the plan owner (provider) to modify or delete it.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.provider == request.user or request.user.is_staff
