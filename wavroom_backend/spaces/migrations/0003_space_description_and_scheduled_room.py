from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('spaces', '0002_space_add_slug'),
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='space',
            name='description',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.CreateModel(
            name='ScheduledRoom',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=300)),
                ('description', models.TextField(blank=True)),
                ('scheduled_at', models.DateTimeField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('space', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='scheduled_rooms',
                    to='spaces.space',
                )),
                ('host', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='hosted_scheduled_rooms',
                    to='users.user',
                )),
            ],
            options={'db_table': 'scheduled_rooms', 'ordering': ['scheduled_at']},
        ),
    ]
