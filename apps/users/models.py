from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone

class Role(models.TextChoices):
    CUSTOMER = 'CUSTOMER', 'Customer'
    PROVIDER = 'PROVIDER', 'Provider'
    ADMIN = 'ADMIN', 'Admin'

class UserManager(BaseUserManager):
    """Custom manager for email-based authentication."""
    
    def create_user(self, email, password=None, role=Role.CUSTOMER, **extra_fields):
        if not email:
            raise ValueError('An email address is required')
        email = self.normalize_email(email).lower()
        extra_fields.setdefault('is_active', True)
        user = self.model(email=email, role=role, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', Role.ADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

class User(AbstractBaseUser, PermissionsMixin):
    """Custom user model supporting Customer, Provider, and Admin roles."""
    email = models.EmailField(unique=True, db_index=True, max_length=255)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CUSTOMER,
        db_index=True,
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-date_joined']

    def __str__(self):
        return f"{self.email} ({self.role})"

    @property
    def is_provider(self):
        return self.role == Role.PROVIDER

    @property
    def is_customer(self):
        return self.role == Role.CUSTOMER

    @property
    def is_admin_role(self):
        return self.role == Role.ADMIN or self.is_superuser
