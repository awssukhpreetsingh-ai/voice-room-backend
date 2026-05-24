from django.core.management.base import BaseCommand
from django.contrib.auth.models import User as DjangoUser
from admin_panel.models import AdminProfile


class Command(BaseCommand):
    help = 'Create an admin user for the WavRoom admin dashboard'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str)
        parser.add_argument('email',    type=str)
        parser.add_argument('password', type=str)
        parser.add_argument(
            '--role',
            type=str,
            default='super_admin',
            choices=['super_admin', 'moderator'],
            help='Admin role (default: super_admin)',
        )

    def handle(self, *args, **options):
        username = options['username']
        email    = options['email']
        password = options['password']
        role     = options['role']

        if DjangoUser.objects.filter(username=username).exists():
            self.stderr.write(f'User "{username}" already exists.')
            return

        django_user = DjangoUser.objects.create_user(
            username=username,
            email=email,
            password=password,
        )
        AdminProfile.objects.create(django_user=django_user, role=role)

        self.stdout.write(self.style.SUCCESS(
            f'Admin "{username}" created with role "{role}".'
        ))
