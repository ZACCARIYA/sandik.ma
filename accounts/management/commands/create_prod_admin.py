from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
import os

User = get_user_model()

class Command(BaseCommand):
    help = 'Create a superuser for production if it does not exist'

    def handle(self, *args, **options):
        username = os.getenv('ADMIN_USERNAME', 'admin')
        email = os.getenv('ADMIN_EMAIL', 'admin@example.com')
        password = os.getenv('ADMIN_PASSWORD', 'admin123456')

        if not User.objects.filter(username=username).exists():
            self.stdout.write(f'Creating superuser {username}...')
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password,
                role='SUPERADMIN'
            )
            self.stdout.write(self.style.SUCCESS(f'Successfully created superuser {username}'))
        else:
            self.stdout.write(self.style.WARNING(f'Superuser {username} already exists'))
