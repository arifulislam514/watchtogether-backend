from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('videos', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='video',
            name='progress',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='video',
            name='stage',
            field=models.CharField(blank=True, max_length=50),
        ),
    ]
