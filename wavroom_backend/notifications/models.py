import uuid
from django.db import models


class Notification(models.Model):
    class Type(models.TextChoices):
        ROOM_STARTED   = 'room_started',   'Room Started'
        NEW_FOLLOWER   = 'new_follower',   'New Follower'
        ROOM_INVITE    = 'room_invite',    'Room Invite'
        SCHEDULED_ROOM = 'scheduled_room', 'Scheduled Room'
        SPACE_ACTIVITY = 'space_activity', 'Space Activity'

    id                = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient         = models.ForeignKey(
        'users.User', on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=30, choices=Type.choices)
    title             = models.CharField(max_length=200)
    body              = models.CharField(max_length=400)
    data              = models.JSONField(default=dict)
    is_read           = models.BooleanField(default=False)
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notifications'
        ordering = ['-created_at']
        indexes  = [
            models.Index(fields=['recipient', 'is_read'],    name='notif_recipient_read_idx'),
            models.Index(fields=['recipient', 'created_at'], name='notif_recipient_created_idx'),
        ]

    def __str__(self):
        return f'[{self.notification_type}] → {self.recipient_id}'

    def to_dict(self):
        return {
            'id':                str(self.id),
            'notification_type': self.notification_type,
            'title':             self.title,
            'body':              self.body,
            'data':              self.data,
            'is_read':           self.is_read,
            'created_at':        self.created_at.isoformat(),
        }
