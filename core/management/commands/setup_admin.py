from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import University

User = get_user_model()

class Command(BaseCommand):
    help = 'Создает администратора и привязывает его к новому Университету'

    def handle(self, *args, **options):
        # 1. Спрашиваем название универа
        uni_name = input('Введите название Университета (например, ТУИТ): ')
        uni, created = University.objects.get_or_create(name=uni_name)

        # 2. Спрашиваем данные админа
        username = input('Логин администратора: ')
        password = input('Пароль: ')

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.ERROR('Пользователь с таким логином уже существует!'))
            return

        # 3. Создаем суперпользователя и привязываем к универу
        user = User.objects.create_superuser(username=username, email='', password=password)
        user.university = uni
        user.is_admin = True
        user.save()

        self.stdout.write(self.style.SUCCESS(f'Успешно! Университет "{uni.name}" и админ "{username}" созданы.'))