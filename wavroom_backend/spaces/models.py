import uuid
from django.db import models
from django.utils.text import slugify


class Space(models.Model):
    ATMOSPHERE_CHOICES = [
        ('philosophy',      'Philosophy'),
        ('ai_research',     'AI Research'),
        ('deep_science',    'Deep Science'),
        ('psychology',      'Psychology'),
        ('entrepreneurship','Entrepreneurship'),
    ]

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug         = models.SlugField(max_length=100, unique=True, blank=True)
    title        = models.CharField(max_length=200)
    tagline      = models.CharField(max_length=300, blank=True)
    description  = models.TextField(blank=True, default='')
    emoji        = models.CharField(max_length=10, default='💬')
    atmosphere   = models.CharField(max_length=50, choices=ATMOSPHERE_CHOICES, default='philosophy')
    accent_color      = models.CharField(max_length=10, default='#7C6FF7')
    cover_image_url   = models.CharField(max_length=500, blank=True, default='')
    energy_score      = models.FloatField(default=0.0)
    energy_updated_at = models.DateTimeField(null=True, blank=True)
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'spaces'

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)
            slug = base
            n = 1
            while Space.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{n}'
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def member_count(self):
        return SpaceMembership.objects.filter(space=self).count()

    def _live_chamber_count(self):
        try:
            from rooms import redis_client as rc
            rc.prune_expired()
            return sum(1 for r in rc.get_all_rooms() if r.get('space_id') == self.slug)
        except Exception:
            return 0

    def _get_live_rooms(self):
        try:
            from rooms import redis_client as rc
            rc.prune_expired()
            return [r for r in rc.get_all_rooms() if r.get('space_id') == self.slug]
        except Exception:
            return []

    def to_dict(self, current_user=None):
        # Resolve the current user's membership and role
        user_membership = None
        if current_user:
            try:
                user_membership = SpaceMembership.objects.get(space=self, user=current_user)
            except SpaceMembership.DoesNotExist:
                pass

        featured = [
            {
                'id':           str(m.user.id),
                'name':         m.user.name,
                'role':         m.role,
                'avatar_color': m.user.avatar_color,
                'avatar_url':   m.user.avatar_url or '',
                'realm_name':   self.title,
            }
            for m in SpaceMembership.objects.filter(
                space=self, role__in=['owner', 'superhost']
            ).select_related('user')
        ]

        return {
            'id':                 self.slug,
            'title':              self.title,
            'tagline':            self.tagline,
            'description':        self.description,
            'emoji':              self.emoji,
            'atmosphere':         self.atmosphere,
            'accent_color':       self.accent_color,
            'cover_image_url':    self.cover_image_url or '',
            'member_count':       self.member_count,
            'live_chamber_count': self._live_chamber_count(),
            'is_member':          user_membership is not None,
            'user_role':          user_membership.role if user_membership else None,
            'curators':           featured,
            'energy_score':       round(self.energy_score, 1),
        }


class SpaceMembership(models.Model):
    ROLE_CHOICES = [
        ('owner',     'Owner'),
        ('superhost', 'SuperHost'),
        ('member',    'Member'),
    ]

    space     = models.ForeignKey(Space, on_delete=models.CASCADE, related_name='memberships')
    user      = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='space_memberships')
    role      = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table        = 'space_memberships'
        unique_together = ('space', 'user')

    def can_create_room(self):
        return self.role in ('owner', 'superhost')

    def is_moderator(self):
        return self.role in ('owner', 'superhost')


class ScheduledRoom(models.Model):
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    space        = models.ForeignKey(Space, on_delete=models.CASCADE, related_name='scheduled_rooms')
    host         = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='hosted_scheduled_rooms')
    title        = models.CharField(max_length=300)
    description  = models.TextField(blank=True)
    scheduled_at = models.DateTimeField()
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'scheduled_rooms'
        ordering = ['scheduled_at']

    def to_dict(self):
        return {
            'id':           str(self.id),
            'title':        self.title,
            'description':  self.description,
            'scheduled_at': self.scheduled_at.isoformat(),
            'host': {
                'id':           str(self.host.id),
                'name':         self.host.name,
                'avatar_color': self.host.avatar_color,
            },
        }


class Discussion(models.Model):
    POST_TYPE_CHOICES = [
        ('thought',   'Thought'),
        ('question',  'Question'),
        ('insight',   'Insight'),
        ('reference', 'Reference'),
    ]
    ATMOSPHERE_CHOICES = [
        ('calm',        'Calm'),
        ('heated',      'Heated'),
        ('beginner',    'Beginner Friendly'),
        ('deep_theory', 'Deep Theory'),
        ('exploratory', 'Exploratory'),
    ]

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    space        = models.ForeignKey(Space, on_delete=models.CASCADE, related_name='discussions')
    author       = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='discussions')
    title        = models.CharField(max_length=300)
    body         = models.TextField()
    tags         = models.JSONField(default=list)
    post_type    = models.CharField(max_length=20, choices=POST_TYPE_CHOICES, default='thought')
    atmosphere   = models.CharField(max_length=20, choices=ATMOSPHERE_CHOICES, default='calm')
    accent_color = models.CharField(max_length=10, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'discussions'
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def _author_role(self):
        try:
            m = SpaceMembership.objects.get(space=self.space, user=self.author)
            return m.role
        except SpaceMembership.DoesNotExist:
            return 'member'

    def to_dict(self, current_user=None):
        reactions = {
            'appreciate': DiscussionReaction.objects.filter(discussion=self, reaction_type='appreciate').count(),
            'insightful': DiscussionReaction.objects.filter(discussion=self, reaction_type='insightful').count(),
            'curious':    DiscussionReaction.objects.filter(discussion=self, reaction_type='curious').count(),
        }

        user_membership = None
        if current_user:
            try:
                user_membership = SpaceMembership.objects.get(space=self.space, user=current_user)
            except SpaceMembership.DoesNotExist:
                pass

        return {
            'id':             str(self.id),
            'space_id':       self.space.slug,
            'space_name':     self.space.title,
            'space_emoji':    self.space.emoji,
            'title':          self.title,
            'body':           self.body,
            'tags':           self.tags,
            'post_type':      self.post_type,
            'atmosphere':     self.atmosphere,
            'accent_color':   self.accent_color or self.space.accent_color,
            'author': {
                'id':           str(self.author.id),
                'name':         self.author.name,
                'role':         self._author_role(),
                'avatar_color': self.author.avatar_color,
                'avatar_url':   self.author.avatar_url or '',
                'realm_name':   self.space.title,
            },
            'created_at':    self.created_at.isoformat(),
            'reactions':     reactions,
            'comment_count': Comment.objects.filter(discussion=self, parent=None).count(),
            'is_saved':      (
                SavedDiscussion.objects.filter(discussion=self, user=current_user).exists()
                if current_user else False
            ),
            'user_is_member': user_membership is not None,
        }


class Comment(models.Model):
    id                     = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    discussion             = models.ForeignKey(Discussion, on_delete=models.CASCADE, related_name='comments')
    author                 = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='comments')
    body                   = models.TextField()
    parent                 = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies')
    is_curator_pick        = models.BooleanField(default=False)
    is_highlighted_insight = models.BooleanField(default=False)
    created_at             = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'comments'
        ordering = ['created_at']

    def _author_role(self):
        try:
            m = SpaceMembership.objects.get(space=self.discussion.space, user=self.author)
            return m.role
        except SpaceMembership.DoesNotExist:
            return 'member'

    def to_dict(self):
        reactions = {
            'appreciate': CommentReaction.objects.filter(comment=self, reaction_type='appreciate').count(),
            'insightful': CommentReaction.objects.filter(comment=self, reaction_type='insightful').count(),
            'curious':    CommentReaction.objects.filter(comment=self, reaction_type='curious').count(),
        }
        replies = [r.to_dict() for r in self.replies.all()] if self.parent is None else []
        return {
            'id':     str(self.id),
            'author': {
                'id':           str(self.author.id),
                'name':         self.author.name,
                'role':         self._author_role(),
                'avatar_color': self.author.avatar_color,
                'avatar_url':   self.author.avatar_url or '',
                'realm_name':   self.discussion.space.title,
            },
            'body':                   self.body,
            'created_at':             self.created_at.isoformat(),
            'reactions':              reactions,
            'replies':                replies,
            'is_curator_pick':        self.is_curator_pick,
            'is_highlighted_insight': self.is_highlighted_insight,
        }


class DiscussionReaction(models.Model):
    REACTION_CHOICES = [
        ('appreciate', 'Appreciate'),
        ('insightful', 'Insightful'),
        ('curious',    'Curious'),
    ]
    discussion    = models.ForeignKey(Discussion, on_delete=models.CASCADE, related_name='reactions')
    user          = models.ForeignKey('users.User', on_delete=models.CASCADE)
    reaction_type = models.CharField(max_length=20, choices=REACTION_CHOICES)

    class Meta:
        db_table        = 'discussion_reactions'
        unique_together = ('discussion', 'user', 'reaction_type')


class CommentReaction(models.Model):
    REACTION_CHOICES = [
        ('appreciate', 'Appreciate'),
        ('insightful', 'Insightful'),
        ('curious',    'Curious'),
    ]
    comment       = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='reactions')
    user          = models.ForeignKey('users.User', on_delete=models.CASCADE)
    reaction_type = models.CharField(max_length=20, choices=REACTION_CHOICES)

    class Meta:
        db_table        = 'comment_reactions'
        unique_together = ('comment', 'user', 'reaction_type')


class SavedDiscussion(models.Model):
    discussion = models.ForeignKey(Discussion, on_delete=models.CASCADE, related_name='saves')
    user       = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='saved_discussions')
    saved_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table        = 'saved_discussions'
        unique_together = ('discussion', 'user')


class SpaceReport(models.Model):
    REASON_CHOICES = [
        ('spam',          'Spam or misleading content'),
        ('harassment',    'Harassment or abusive behavior'),
        ('hate_speech',   'Hate speech or harmful discussions'),
        ('inappropriate', 'Inappropriate content'),
        ('fake_quality',  'Fake or low-quality community'),
        ('other',         'Other'),
    ]

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    space      = models.ForeignKey(Space, on_delete=models.CASCADE, related_name='reports')
    reporter   = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='space_reports')
    reason     = models.CharField(max_length=20, choices=REASON_CHOICES)
    message    = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table        = 'space_reports'
        unique_together = ('space', 'reporter')
