import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('spaces', '0004_merge_20260517_0525'),
    ]

    operations = [
        migrations.CreateModel(
            name='SpaceReport',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('reason', models.CharField(choices=[
                    ('spam',          'Spam or misleading content'),
                    ('harassment',    'Harassment or abusive behavior'),
                    ('hate_speech',   'Hate speech or harmful discussions'),
                    ('inappropriate', 'Inappropriate content'),
                    ('fake_quality',  'Fake or low-quality community'),
                    ('other',         'Other'),
                ], max_length=20)),
                ('message', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reporter', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='space_reports',
                    to='users.user',
                )),
                ('space', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='reports',
                    to='spaces.space',
                )),
            ],
            options={'db_table': 'space_reports'},
        ),
        migrations.AlterUniqueTogether(
            name='spacereport',
            unique_together={('space', 'reporter')},
        ),
    ]
