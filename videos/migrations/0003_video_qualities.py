from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('videos', '0002_video_progress_stage'),
    ]

    operations = [
        migrations.AddField(
            model_name='video',
            name='url_480p',
            field=models.URLField(blank=True),
        ),
        migrations.AddField(
            model_name='video',
            name='qualities',
            field=models.JSONField(default=list),
        ),
    ]
