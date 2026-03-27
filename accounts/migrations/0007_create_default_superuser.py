from django.db import migrations
from django.contrib.auth.hashers import make_password
import os

def create_default_superuser(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    username = os.getenv('ADMIN_USERNAME', 'admin')
    email = os.getenv('ADMIN_EMAIL', 'admin@example.com')
    password = os.getenv('ADMIN_PASSWORD', 'admin123456')

    if not User.objects.filter(username=username).exists():
        User.objects.create(
            username=username,
            email=email,
            password=make_password(password),
            is_superuser=True,
            is_staff=True,
            role='SUPERADMIN',
            is_active=True
        )

def remove_default_superuser(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    username = os.getenv('ADMIN_USERNAME', 'admin')
    User.objects.filter(username=username).delete()

class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0006_user_accounts_us_role_1fa9a5_idx_and_more'),
    ]

    operations = [
        migrations.RunPython(create_default_superuser, remove_default_superuser),
    ]
