from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='totp_secret',
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='totp_enabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='user',
            name='totp_backup_codes',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='user',
            name='last_totp_failure',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='totp_failure_count',
            field=models.IntegerField(default=0),
        ),
    ]
