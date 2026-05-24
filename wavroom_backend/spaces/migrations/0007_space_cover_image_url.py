from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('spaces', '0006_alter_spacemembership_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='space',
            name='cover_image_url',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
    ]
