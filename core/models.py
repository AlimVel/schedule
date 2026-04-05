import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser


class University(models.Model):
    name = models.CharField(max_length=255, verbose_name="Название университета")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class User(AbstractUser):
    university = models.ForeignKey(
        'University', on_delete=models.CASCADE, null=True, blank=True
    )
    is_admin = models.BooleanField(default=False, verbose_name="Администратор ВУЗа")
    is_teacher = models.BooleanField(default=False, verbose_name="Преподаватель")
    middle_name = models.CharField(
        max_length=150, blank=True, null=True, verbose_name="Отчество"
    )
    academic_title = models.CharField(
        max_length=50, blank=True, null=True, verbose_name="Научное звание"
    )

    def __str__(self):
        return self.get_full_name() or self.username


class InviteLink(models.Model):
    university = models.ForeignKey(University, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Инвайт для {self.university.name} ({self.token})"


# ──────────────────────────────────────────────────────────────
#  Структура университета
# ──────────────────────────────────────────────────────────────

class Direction(models.Model):
    """Направление (факультет / специальность)."""
    university = models.ForeignKey(
        University, on_delete=models.CASCADE, related_name='directions'
    )
    name = models.CharField(max_length=255, verbose_name="Название направления")

    def __str__(self):
        return f"{self.university.name} / {self.name}"


class Course(models.Model):
    """Курс внутри направления (1–4/5)."""
    direction = models.ForeignKey(
        Direction, on_delete=models.CASCADE, related_name='courses'
    )
    number = models.PositiveSmallIntegerField(verbose_name="Номер курса")

    class Meta:
        unique_together = ('direction', 'number')

    def __str__(self):
        return f"{self.direction.name} — {self.number} курс"



class Group(models.Model):
    """Студенческая группа внутри курса."""
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name='groups'
    )
    name = models.CharField(max_length=100, verbose_name="Название группы",
                            help_text="Например: ПМИ-301")

    class Meta:
        unique_together = ('course', 'name')
        ordering = ['name']

    def __str__(self):
        return self.name


class Classroom(models.Model):
    """Аудитория."""
    university = models.ForeignKey(
        University, on_delete=models.CASCADE, related_name='classrooms'
    )
    name = models.CharField(max_length=100, verbose_name="Номер / название аудитории")
    capacity = models.PositiveIntegerField(default=30, verbose_name="Вместимость")

    def __str__(self):
        return f"{self.name} ({self.university.name})"


# ──────────────────────────────────────────────────────────────
#  Предметы
# ──────────────────────────────────────────────────────────────

class Subject(models.Model):
    """Предмет / дисциплина."""
    university = models.ForeignKey(
        University, on_delete=models.CASCADE, related_name='subjects'
    )
    name = models.CharField(max_length=255, verbose_name="Название предмета")
    teacher = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        limit_choices_to={'is_teacher': True},
        related_name='subjects',
        verbose_name="Преподаватель"
    )
    difficulty_points = models.PositiveSmallIntegerField(
        default=1,
        verbose_name="Сложность (баллы)",
        help_text="1 — лёгкий, 5 — очень сложный"
    )
    hours_per_semester = models.PositiveSmallIntegerField(
        default=36, verbose_name="Часов в семестре"
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='subjects',
        verbose_name="Курс"
    )

    def __str__(self):
        return self.name


# ──────────────────────────────────────────────────────────────
#  Расписание (Schedule)
# ──────────────────────────────────────────────────────────────

WEEKDAYS = [
    (0, 'Понедельник'),
    (1, 'Вторник'),
    (2, 'Среда'),
    (3, 'Четверг'),
    (4, 'Пятница'),
    (5, 'Суббота'),
]

LESSON_TYPES = [
    ('lecture',  'Лекция'),
    ('practice', 'Практика'),
    ('lab',      'Лабораторная'),
    ('seminar',  'Семинар'),
    ('online',   'Онлайн'),
]

class ScheduleEntry(models.Model):
    """Одна запись расписания — конкретный слот пары."""
    university = models.ForeignKey(
        University, on_delete=models.CASCADE, related_name='schedule_entries'
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name='schedule_entries'
    )
    teacher = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={'is_teacher': True},
        related_name='schedule_entries'
    )
    classroom = models.ForeignKey(
        Classroom, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='schedule_entries'
    )
    course = models.ForeignKey(
        Course, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='schedule_entries'
    )
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAYS, verbose_name="День недели")
    slot_number = models.PositiveSmallIntegerField(
        verbose_name="Номер пары",
        help_text="1=08:30, 2=10:15, 3=12:00, 4=13:45, 5=15:30, 6=17:15"
    )
    lesson_type = models.CharField(
        max_length=20, choices=LESSON_TYPES, default='lecture', verbose_name="Тип занятия"
    )
    is_approved = models.BooleanField(default=False, verbose_name="Подтверждено")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # Нельзя поставить одного преподавателя дважды в один слот
        unique_together = ('teacher', 'weekday', 'slot_number')
        ordering = ['weekday', 'slot_number']

    def __str__(self):
        return (
            f"{self.get_weekday_display()} пара {self.slot_number} — "
            f"{self.subject.name} ({self.teacher})"
        )


# ──────────────────────────────────────────────────────────────
#  Пожелания преподавателя
# ──────────────────────────────────────────────────────────────

class TeacherPreference(models.Model):
    """Матрица доступности и лимиты нагрузки преподавателя."""
    teacher = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        limit_choices_to={'is_teacher': True},
        related_name='preference'
    )
    max_lessons_per_day = models.PositiveSmallIntegerField(
        default=4, verbose_name="Макс. пар в день"
    )
    max_consecutive_lessons = models.PositiveSmallIntegerField(
        default=2, verbose_name="Макс. пар подряд"
    )
    # JSON-поле: список заблокированных слотов вида [{"weekday": 0, "slot": 1}, ...]
    blocked_slots = models.JSONField(
        default=list, blank=True, verbose_name="Заблокированные слоты"
    )
    # JSON-поле: список предпочтительных слотов
    preferred_slots = models.JSONField(
        default=list, blank=True, verbose_name="Предпочтительные слоты"
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Пожелания: {self.teacher}"