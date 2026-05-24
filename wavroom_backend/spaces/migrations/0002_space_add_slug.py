from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('spaces', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='space',
            name='slug',
            field=models.SlugField(max_length=100, unique=True, default=''),
            preserve_default=False,
        ),
    ]
