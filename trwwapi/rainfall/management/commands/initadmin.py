from os import getenv
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

class Command(BaseCommand):

    def handle(self, *args, **options):
        
        username = getenv('DJANGO_SUPERUSER_USERNAME', None)
        email = getenv('DJANGO_SUPERUSER_EMAIL', None)
        password = getenv('DJANGO_SUPERUSER_PASSWORD', None)

        if all([username, email, password]):
            if not User.objects.filter(username=username).exists():
                self.stdout.write(f'Creating superuser account for {username} ({email})')
                admin = User.objects.create_superuser(
                    email=email, username=username, password=password
                )
            else:
                self.stdout.write('Superuser exists.')
        else:
            self.stdout.write("Could not create superuser account. DJANGO_SUPERUSER_* environment variables not present.")