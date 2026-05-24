from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0005_user_is_banned'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='name_updated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='avatar_updated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='cover_updated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
