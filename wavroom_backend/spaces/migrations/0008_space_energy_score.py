from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('spaces', '0007_space_cover_image_url'),
    ]

    operations = [
        migrations.AddField(
            model_name='space',
            name='energy_score',
            field=models.FloatField(default=0.0),
        ),
        migrations.AddField(
            model_name='space',
            name='energy_updated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
