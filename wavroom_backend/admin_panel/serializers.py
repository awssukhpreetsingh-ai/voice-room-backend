from rest_framework import serializers
from users.models import User, Follow
from spaces.models import Space, SpaceMembership, Discussion, SpaceReport
from .models import AdminProfile, AuditLog


class AdminProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='django_user.username')
    email    = serializers.EmailField(source='django_user.email')

    class Meta:
        model  = AdminProfile
        fields = ['id', 'username', 'email', 'role', 'is_active', 'created_at']


class UserAdminSerializer(serializers.ModelSerializer):
    follower_count  = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = [
            'id', 'name', 'username', 'email', 'phone', 'gender', 'bio',
            'avatar_url', 'avatar_color', 'interests', 'talks_hosted',
            'reputation_score', 'onboarding_complete', 'is_banned',
            'created_at', 'updated_at', 'follower_count', 'following_count',
        ]

    def get_follower_count(self, obj):
        return Follow.objects.filter(following=obj).count()

    def get_following_count(self, obj):
        return Follow.objects.filter(follower=obj).count()


class SpaceAdminSerializer(serializers.ModelSerializer):
    member_count = serializers.SerializerMethodField()
    owner        = serializers.SerializerMethodField()

    class Meta:
        model  = Space
        fields = [
            'id', 'slug', 'title', 'tagline', 'emoji', 'atmosphere',
            'accent_color', 'cover_image_url', 'created_at', 'member_count', 'owner',
        ]

    def get_member_count(self, obj):
        return SpaceMembership.objects.filter(space=obj).count()

    def get_owner(self, obj):
        m = SpaceMembership.objects.filter(space=obj, role='owner').select_related('user').first()
        if m:
            return {'id': str(m.user.id), 'name': m.user.name, 'email': m.user.email}
        return None


class ReportAdminSerializer(serializers.ModelSerializer):
    reporter_name  = serializers.CharField(source='reporter.name')
    reporter_email = serializers.CharField(source='reporter.email')
    space_title    = serializers.CharField(source='space.title')
    space_slug     = serializers.CharField(source='space.slug')

    class Meta:
        model  = SpaceReport
        fields = [
            'id', 'space_id', 'space_title', 'space_slug',
            'reporter_name', 'reporter_email', 'reason', 'message', 'created_at',
        ]


class AuditLogSerializer(serializers.ModelSerializer):
    admin_username = serializers.SerializerMethodField()

    class Meta:
        model  = AuditLog
        fields = ['id', 'admin_username', 'action', 'target_type', 'target_id', 'details', 'ip_address', 'timestamp']

    def get_admin_username(self, obj):
        if obj.admin:
            return obj.admin.django_user.username
        return None
