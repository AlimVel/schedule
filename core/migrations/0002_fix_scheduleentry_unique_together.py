from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='scheduleentry',
            unique_together={('teacher', 'weekday', 'slot_number', 'week_number')},
        ),
    ]