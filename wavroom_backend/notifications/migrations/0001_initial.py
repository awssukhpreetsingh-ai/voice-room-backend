import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('users', '0005_user_is_banned'),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('notification_type', models.CharField(
                    choices=[
                        ('room_started',   'Room Started'),
                        ('new_follower',   'New Follower'),
                        ('room_invite',    'Room Invite'),
                        ('scheduled_room', 'Scheduled Room'),
                        ('space_activity', 'Space Activity'),
                    ],
                    max_length=30,
                )),
                ('title',      models.CharField(max_length=200)),
                ('body',       models.CharField(max_length=400)),
                ('data',       models.JSONField(default=dict)),
                ('is_read',    models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('recipient',  models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notifications',
                    to='users.user',
                )),
            ],
            options={
                'db_table': 'notifications',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(
                fields=['recipient', 'is_read'],
                name='notif_recipient_read_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(
                fields=['recipient', 'created_at'],
                name='notif_recipient_created_idx',
            ),
        ),
    ]
