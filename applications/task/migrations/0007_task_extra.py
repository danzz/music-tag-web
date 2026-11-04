from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('task', '0006_auto_20230830_1458'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='extra',
            field=models.TextField(default=''),
        ),
    ]

