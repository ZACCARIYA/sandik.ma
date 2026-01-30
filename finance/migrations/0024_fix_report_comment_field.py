# Generated manually to fix column name mismatch
# This migration is a no-op since the field is already named 'comment' in migration 0022

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0023_auto_20250928_0614'),
    ]

    operations = [
        # No operation needed - field is already named 'comment'
    ]
