from django.db import migrations, models
from django.conf import settings
import uuid

class Migration(migrations.Migration):
    dependencies = [
        ('security', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    
    operations = [
        migrations.CreateModel(
            name='SecurityAudit',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, primary_key=True)),
                ('action', models.CharField(max_length=100)),
                ('resource_type', models.CharField(max_length=50)),
                ('resource_id', models.CharField(max_length=100)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)),
                ('circuit_fingerprint', models.CharField(max_length=64)),
                ('user_agent', models.TextField()),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('success', models.BooleanField(default=True)),
                ('details', models.JSONField(default=dict)),
            ],
        ),
    ]
