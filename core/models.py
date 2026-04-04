import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser

# 1. Модель Университета
class University(models.Model):
    name = models.CharField(max_length=255, verbose_name="Название университета")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class User(AbstractUser):
    university = models.ForeignKey(University, on_delete=models.CASCADE, null=True, blank=True)
    is_admin = models.BooleanField(default=False, verbose_name="Администратор ВУЗа")
    is_teacher = models.BooleanField(default=False, verbose_name="Преподаватель")
    
    middle_name = models.CharField(max_length=150, blank=True, null=True, verbose_name="Отчество")
    academic_title = models.CharField(max_length=50, blank=True, null=True, verbose_name="Научное звание")

# 3. Модель для генерации инвайт-ссылок
class InviteLink(models.Model):
    university = models.ForeignKey(University, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Инвайт для {self.university.name} ({self.token})"