from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from app.models import Profile, Role


class Command(BaseCommand):
    help = 'Создаёт суперпользователя root/root'

    def handle(self, *args, **options):
        user, created = User.objects.get_or_create(
            username='root',
            defaults={'is_staff': True, 'is_superuser': True},
        )
        if created:
            user.set_password('root')
            user.save()
            Profile.objects.get_or_create(
                user=user,
                defaults={'full_name': 'Администратор', 'role': Role.ADMIN},
            )
            self.stdout.write(self.style.SUCCESS('Создан: root/root'))
        else:
            if not user.check_password('root'):
                user.set_password('root')
                user.save()
            if not user.is_superuser:
                user.is_superuser = True
                user.is_staff = True
                user.save()
            Profile.objects.get_or_create(
                user=user,
                defaults={'full_name': 'Администратор', 'role': Role.ADMIN},
            )
            self.stdout.write(self.style.SUCCESS('Уже существует, пароль сброшен: root/root'))
