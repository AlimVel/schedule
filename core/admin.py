from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    User, University, InviteLink, Direction, Course, Group,
    Classroom, Subject, ScheduleEntry, TeacherPreference
)

# Регистрация кастомного юзера (чтобы пароли хэшировались при смене через админку)
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Дополнительно', {'fields': ('university', 'is_admin', 'is_teacher', 'middle_name', 'academic_title')}),
    )
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_teacher', 'is_admin', 'university')
    list_filter = ('is_teacher', 'is_admin', 'university')

# Регистрация остальных моделей
admin.site.register(University)
admin.site.register(InviteLink)
admin.site.register(Direction)
admin.site.register(Course)
admin.site.register(Group)
admin.site.register(Classroom)
admin.site.register(Subject)
admin.site.register(ScheduleEntry)
admin.site.register(TeacherPreference) 