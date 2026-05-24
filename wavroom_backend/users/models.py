
# import uuid
# from django.db import models


# class User(models.Model):
#     id                  = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     firebase_uid        = models.CharField(max_length=128, unique=True, db_index=True)
#     name                = models.CharField(max_length=100, blank=True, default='')
#     phone               = models.CharField(max_length=20,  blank=True, default='')
#     email               = models.EmailField(blank=True, default='')
#     gender              = models.CharField(max_length=30,  blank=True, default='')
#     interests           = models.JSONField(default=list,   blank=True)
#     bio                 = models.TextField(blank=True, default='')
#     avatar_color        = models.CharField(max_length=10,  default='#7C3AED')
#     linkedin_url        = models.URLField(blank=True, default='')
#     twitter_url         = models.URLField(blank=True, default='')
#     website_url         = models.URLField(blank=True, default='')
#     onboarding_complete = models.BooleanField(default=False)
#     created_at          = models.DateTimeField(auto_now_add=True)
#     updated_at          = models.DateTimeField(auto_now=True)

#     class Meta:
#         db_table = 'users'

#     def __str__(self):
#         return self.name or self.firebase_uid

#     @property
#     def initials(self):
#         n = self.name.strip()
#         if not n:
#             return '??'
#         parts = n.split()
#         if len(parts) >= 2:
#             return f'{parts[0][0]}{parts[1][0]}'.upper()
#         return n[:2].upper()

#     @property
#     def follower_count(self):
#         return Follow.objects.filter(following=self).count()

#     @property
#     def following_count(self):
#         return Follow.objects.filter(follower=self).count()

#     def to_dict(self, current_user=None):
#         data = {
#             'id':                   str(self.id),
#             'firebase_uid':         self.firebase_uid,
#             'name':                 self.name,
#             'phone':                self.phone,
#             'email':                self.email,
#             'gender':               self.gender,
#             'interests':            self.interests,
#             'bio':                  self.bio,
#             'avatar_color':         self.avatar_color,
#             'linkedin_url':         self.linkedin_url,
#             'twitter_url':          self.twitter_url,
#             'website_url':          self.website_url,
#             'initials':             self.initials,
#             'follower_count':       self.follower_count,
#             'following_count':      self.following_count,
#             'onboarding_complete':  self.onboarding_complete,
#         }
#         # If we know who is viewing, include is_following
#         if current_user and current_user.id != self.id:
#             data['is_following'] = Follow.objects.filter(
#                 follower=current_user,
#                 following=self,
#             ).exists()
#         else:
#             data['is_following'] = False
#         return data


# class Follow(models.Model):
#     follower  = models.ForeignKey(
#         User, on_delete=models.CASCADE, related_name='following_set')
#     following = models.ForeignKey(
#         User, on_delete=models.CASCADE, related_name='follower_set')
#     created_at = models.DateTimeField(auto_now_add=True)

#     class Meta:
#         db_table = 'follows'
#         unique_together = ('follower', 'following')

#     def __str__(self):
#         return f'{self.follower.name} → {self.following.name}'



import uuid
from django.db import models


class User(models.Model):
    id                  = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    firebase_uid        = models.CharField(max_length=128, unique=True, db_index=True)
    name                = models.CharField(max_length=100, blank=True, default='')
    phone               = models.CharField(max_length=20,  blank=True, default='')
    email               = models.EmailField(blank=True, default='')
    gender              = models.CharField(max_length=30,  blank=True, default='')
    interests           = models.JSONField(default=list,   blank=True)
    bio                 = models.TextField(blank=True, default='')
    avatar_color        = models.CharField(max_length=10,  default='#7C3AED')
    linkedin_url        = models.URLField(blank=True, default='')
    twitter_url         = models.URLField(blank=True, default='')
    website_url         = models.URLField(blank=True, default='')
    onboarding_complete = models.BooleanField(default=False)
    fcm_token           = models.TextField(blank=True, default='')
    # Profile identity & media
    username            = models.CharField(max_length=50, blank=True, null=True, unique=True)
    avatar_url          = models.URLField(max_length=500, blank=True, default='')
    cover_image_url     = models.URLField(max_length=500, blank=True, default='')
    # Activity stats
    talks_hosted        = models.IntegerField(default=0)
    reputation_score    = models.IntegerField(default=0)
    is_banned           = models.BooleanField(default=False)
    # Tracks when each protected field was last changed, used for cooldown enforcement.
    name_updated_at     = models.DateTimeField(null=True, blank=True)
    avatar_updated_at   = models.DateTimeField(null=True, blank=True)
    cover_updated_at    = models.DateTimeField(null=True, blank=True)
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'users'

    def __str__(self):
        return self.name or self.firebase_uid

    @property
    def initials(self):
        n = self.name.strip()
        if not n:
            return '??'
        parts = n.split()
        if len(parts) >= 2:
            return f'{parts[0][0]}{parts[1][0]}'.upper()
        return n[:2].upper()

    @property
    def follower_count(self):
        return Follow.objects.filter(following=self).count()

    @property
    def following_count(self):
        return Follow.objects.filter(follower=self).count()

    def to_dict(self, current_user=None):
        data = {
            'id':                   str(self.id),
            'firebase_uid':         self.firebase_uid,
            'name':                 self.name,
            'username':             self.username or '',
            'phone':                self.phone,
            'email':                self.email,
            'gender':               self.gender,
            'interests':            self.interests,
            'bio':                  self.bio,
            'avatar_color':         self.avatar_color,
            'avatar_url':           self.avatar_url or '',
            'cover_image_url':      self.cover_image_url or '',
            'linkedin_url':         self.linkedin_url,
            'twitter_url':          self.twitter_url,
            'website_url':          self.website_url,
            'initials':             self.initials,
            'follower_count':       self.follower_count,
            'following_count':      self.following_count,
            'talks_hosted':         self.talks_hosted,
            'reputation_score':     self.reputation_score,
            'onboarding_complete':  self.onboarding_complete,
            'created_at':           self.created_at.isoformat() if self.created_at else '',
        }
        if current_user and current_user.id != self.id:
            data['is_following'] = Follow.objects.filter(
                follower=current_user, following=self).exists()
        else:
            data['is_following'] = False

        # Expose cooldown state and validation limits for the profile owner only.
        if current_user and current_user.id == self.id:
            data['profile_limits'] = self._profile_limits()

        return data

    def _profile_limits(self) -> dict:
        """Return validation limits and cooldown unlock times for the profile owner."""
        from datetime import timedelta
        from django.utils import timezone
        from . import config as cfg

        now = timezone.now()

        def _next_update_at(last_at, hours):
            if hours <= 0 or last_at is None:
                return None
            unlock = last_at + timedelta(hours=hours)
            return unlock.isoformat() if unlock > now else None

        return {
            'name_next_update_at':   _next_update_at(self.name_updated_at,   cfg.NAME_COOLDOWN_HOURS),
            'avatar_next_update_at': _next_update_at(self.avatar_updated_at, cfg.AVATAR_COOLDOWN_HOURS),
            'cover_next_update_at':  _next_update_at(self.cover_updated_at,  cfg.COVER_COOLDOWN_HOURS),
            'name_min_length':       cfg.NAME_MIN_LENGTH,
            'name_max_length':       cfg.NAME_MAX_LENGTH,
            'name_max_words':        cfg.NAME_MAX_WORDS,
            'bio_max_length':        cfg.BIO_MAX_LENGTH,
            'max_image_size_mb':     cfg.MAX_IMAGE_SIZE_BYTES // (1024 * 1024),
            'allowed_image_formats': sorted(cfg.ALLOWED_IMAGE_EXTENSIONS),
        }


class Follow(models.Model):
    follower  = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='following_set')
    following = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='follower_set')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table     = 'follows'
        unique_together = ('follower', 'following')

    def __str__(self):
        return f'{self.follower.name} → {self.following.name}'