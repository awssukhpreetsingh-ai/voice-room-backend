import secrets
from datetime import timedelta
from django.db import models
from django.contrib.auth.models import User as DjangoUser
from django.utils import timezone


class AdminProfile(models.Model):
    ROLE_CHOICES = [
        ('super_admin', 'Super Admin'),
        ('moderator',   'Moderator'),
    ]

    django_user = models.OneToOneField(
        DjangoUser, on_delete=models.CASCADE, related_name='admin_profile'
    )
    role       = models.CharField(max_length=20, choices=ROLE_CHOICES, default='moderator')
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.django_user.username} ({self.role})'


class AdminToken(models.Model):
    admin      = models.ForeignKey(AdminProfile, on_delete=models.CASCADE, related_name='tokens')
    token      = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def is_valid(self):
        return timezone.now() < self.expires_at

    @classmethod
    def create_for(cls, admin: AdminProfile) -> 'AdminToken':
        cls.objects.filter(admin=admin).delete()
        return cls.objects.create(
            admin=admin,
            token=secrets.token_hex(32),
            expires_at=timezone.now() + timedelta(days=7),
        )


class AuditLog(models.Model):
    admin       = models.ForeignKey(AdminProfile, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action      = models.CharField(max_length=50)
    target_type = models.CharField(max_length=50)
    target_id   = models.CharField(max_length=100)
    details     = models.JSONField(default=dict)
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    timestamp   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
