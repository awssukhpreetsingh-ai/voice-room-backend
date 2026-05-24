from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0003_user_fcm_token'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='username',
            field=models.CharField(blank=True, max_length=50, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='user',
            name='avatar_url',
            field=models.URLField(blank=True, default='', max_length=500),
        ),
        migrations.AddField(
            model_name='user',
            name='cover_image_url',
            field=models.URLField(blank=True, default='', max_length=500),
        ),
        migrations.AddField(
            model_name='user',
            name='talks_hosted',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='user',
            name='reputation_score',
            field=models.IntegerField(default=0),
        ),
    ]
