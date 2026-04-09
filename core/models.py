import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser


# ──────────────────────────────────────────────────────────────
#  University
# ──────────────────────────────────────────────────────────────

class University(models.Model):
    name       = models.CharField(max_length=255, verbose_name="Название университета")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = "Университет"
        verbose_name_plural = "Университеты"

    def __str__(self):
        return self.name


# ──────────────────────────────────────────────────────────────
#  User
# ──────────────────────────────────────────────────────────────

class User(AbstractUser):
    university     = models.ForeignKey(
        University, on_delete=models.CASCADE, null=True, blank=True,
        verbose_name="Университет"
    )
    is_admin       = models.BooleanField(default=False, verbose_name="Администратор ВУЗа")
    is_teacher     = models.BooleanField(default=False, verbose_name="Преподаватель")
    middle_name    = models.CharField(max_length=150, blank=True, null=True, verbose_name="Отчество")
    academic_title = models.CharField(max_length=50,  blank=True, null=True, verbose_name="Научное звание")

    class Meta:
        verbose_name        = "Пользователь"
        verbose_name_plural = "Пользователи"

    def __str__(self):
        return self.get_full_name() or self.username


# ──────────────────────────────────────────────────────────────
#  InviteLink
# ──────────────────────────────────────────────────────────────

class InviteLink(models.Model):
    university = models.ForeignKey(University, on_delete=models.CASCADE, verbose_name="Университет")
    token      = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active  = models.BooleanField(default=True)

    class Meta:
        verbose_name        = "Инвайт-ссылка"
        verbose_name_plural = "Инвайт-ссылки"

    def __str__(self):
        return f"Инвайт для {self.university.name} ({self.token})"


# ──────────────────────────────────────────────────────────────
#  Direction / Course / Group
# ──────────────────────────────────────────────────────────────

class Direction(models.Model):
    university = models.ForeignKey(
        University, on_delete=models.CASCADE, related_name="directions",
        verbose_name="Университет"
    )
    name = models.CharField(max_length=255, verbose_name="Название направления")

    class Meta:
        verbose_name        = "Направление"
        verbose_name_plural = "Направления"

    def __str__(self):
        return f"{self.university.name} / {self.name}"


class Course(models.Model):
    direction = models.ForeignKey(
        Direction, on_delete=models.CASCADE, related_name="courses",
        verbose_name="Направление"
    )
    number = models.PositiveSmallIntegerField(verbose_name="Номер курса")

    class Meta:
        unique_together     = ("direction", "number")
        verbose_name        = "Курс"
        verbose_name_plural = "Курсы"

    def __str__(self):
        return f"{self.direction.name} — {self.number} курс"


class Group(models.Model):
    course   = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="groups",
        verbose_name="Курс"
    )
    name     = models.CharField(max_length=100, verbose_name="Название группы",
                                help_text="Например: ПМИ-301")
    students = models.PositiveSmallIntegerField(default=25, verbose_name="Количество студентов")

    class Meta:
        unique_together     = ("course", "name")
        ordering            = ["name"]
        verbose_name        = "Группа"
        verbose_name_plural = "Группы"

    def __str__(self):
        return self.name


# ──────────────────────────────────────────────────────────────
#  Classroom
# ──────────────────────────────────────────────────────────────

ROOM_TYPES = [
    ("lecture",  "Лекционная"),
    ("seminar",  "Семинарская"),
    ("comp",     "Компьютерный класс"),
    ("special",  "Специализированная"),
]

class Classroom(models.Model):
    university   = models.ForeignKey(
        University, on_delete=models.CASCADE, related_name="classrooms",
        verbose_name="Университет"
    )
    name         = models.CharField(max_length=100, verbose_name="Номер / название")
    capacity     = models.PositiveIntegerField(default=30, verbose_name="Вместимость")
    room_type    = models.CharField(
        max_length=20, choices=ROOM_TYPES, default="seminar",
        verbose_name="Тип аудитории"
    )
    low_priority = models.BooleanField(
        default=False, verbose_name="Низкий приоритет",
        help_text="Использовать только если нет других подходящих аудиторий"
    )

    class Meta:
        verbose_name        = "Аудитория"
        verbose_name_plural = "Аудитории"

    def __str__(self):
        return f"{self.name} ({self.get_room_type_display()}, {self.capacity} мест)"


# ──────────────────────────────────────────────────────────────
#  Subject
# ──────────────────────────────────────────────────────────────

class Subject(models.Model):
    university        = models.ForeignKey(
        University, on_delete=models.CASCADE, related_name="subjects",
        verbose_name="Университет"
    )
    name              = models.CharField(max_length=255, verbose_name="Название предмета")
    teacher           = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        limit_choices_to={"is_teacher": True},
        related_name="subjects", verbose_name="Преподаватель (основной)"
    )
    difficulty_points = models.PositiveSmallIntegerField(
        default=1, verbose_name="Сложность (1–5)",
        help_text="1 — лёгкий, 5 — очень сложный"
    )
    pairs_per_semester = models.PositiveSmallIntegerField(
        default=18, verbose_name="Пар в семестре"
    )
    course            = models.ForeignKey(
        Course, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="subjects", verbose_name="Курс"
    )
    semester          = models.PositiveSmallIntegerField(
        default=1, verbose_name="Семестр"
    )

    class Meta:
        verbose_name        = "Предмет"
        verbose_name_plural = "Предметы"

    def __str__(self):
        return self.name

# ──────────────────────────────────────────────────────────────
#  SubjectConfig  — конфигурация занятий предмета
# ──────────────────────────────────────────────────────────────

class SubjectConfig(models.Model):
    KIND_LECTURE = "lecture"
    KIND_SEMINAR = "seminar"
    KIND_COMP    = "comp"
    KINDS = [
        (KIND_LECTURE, "Лекция"),
        (KIND_SEMINAR, "Семинар"),
        (KIND_COMP,    "Компьютерный класс"),
    ]

    subject      = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="configs",
        verbose_name="Предмет"
    )
    kind         = models.CharField(
        max_length=20, choices=KINDS, default=KIND_LECTURE,
        verbose_name="Вид занятия"
    )
    teacher      = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        limit_choices_to={"is_teacher": True},
        related_name="subject_configs", verbose_name="Преподаватель"
    )
    groups       = models.ManyToManyField(
        Group, blank=True, verbose_name="Группы"
    )
    room_type    = models.CharField(
        max_length=20, choices=ROOM_TYPES, default="seminar",
        verbose_name="Тип аудитории"
    )
    fixed_room   = models.ForeignKey(
        Classroom, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Фиксированная аудитория"
    )
    total_pairs  = models.PositiveSmallIntegerField(
        default=18, verbose_name="Пар за семестр"
    )
    per_group    = models.BooleanField(
        default=False, verbose_name="Отдельно для каждой группы",
        help_text="Преподаватель ведёт занятие отдельно с каждой группой"
    )
    simultaneous = models.BooleanField(
        default=False, verbose_name="Одновременно (подгруппы)",
        help_text="Подгруппы занимаются в одно время в разных аудиториях"
    )
    subgroup_id  = models.CharField(
        max_length=50, blank=True, verbose_name="ID подгруппы",
        help_text="Заполнить если это одна из параллельных подгрупп"
    )
    min_lectures_before_seminars = models.PositiveSmallIntegerField(
        default=0, verbose_name="Мин. лекций перед семинарами"
    )
    lecture_to_seminar_ratio = models.FloatField(
        default=0.5, verbose_name="Соотношение лекция/семинар",
        help_text="0.5 = на 1 лекцию 2 семинара"
    )

    class Meta:
        verbose_name        = "Конфигурация предмета"
        verbose_name_plural = "Конфигурации предметов"

    def __str__(self):
        return f"{self.subject.name} / {self.get_kind_display()}"


# ──────────────────────────────────────────────────────────────
#  ScheduleEntry  — одна запись расписания
# ──────────────────────────────────────────────────────────────

WEEKDAYS = [
    (0, "Понедельник"), (1, "Вторник"), (2, "Среда"),
    (3, "Четверг"),     (4, "Пятница"), (5, "Суббота"),
]

LESSON_TYPES = [
    ("lecture",  "Лекция"),
    ("practice", "Практика"),
    ("lab",      "Лабораторная"),
    ("seminar",  "Семинар"),
    ("online",   "Онлайн"),
]

class ScheduleEntry(models.Model):
    university  = models.ForeignKey(
        University, on_delete=models.CASCADE, related_name="schedule_entries",
        verbose_name="Университет"
    )
    subject     = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="schedule_entries",
        verbose_name="Предмет"
    )
    teacher     = models.ForeignKey(
        User, on_delete=models.CASCADE,
        limit_choices_to={"is_teacher": True},
        related_name="schedule_entries", verbose_name="Преподаватель"
    )
    classroom   = models.ForeignKey(
        Classroom, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="schedule_entries", verbose_name="Аудитория"
    )
    course      = models.ForeignKey(
        Course, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="schedule_entries", verbose_name="Курс"
    )
    groups      = models.ManyToManyField(
        Group, blank=True,
        related_name="schedule_entries", verbose_name="Группы"
    )
    weekday     = models.PositiveSmallIntegerField(
        choices=WEEKDAYS, verbose_name="День недели"
    )
    slot_number = models.PositiveSmallIntegerField(
        verbose_name="Номер пары",
        help_text="1=08:30, 2=10:15, 3=12:00, 4=13:45, 5=15:30, 6=17:15"
    )
    lesson_type = models.CharField(
        max_length=20, choices=LESSON_TYPES, default="lecture",
        verbose_name="Тип занятия"
    )
    is_approved = models.BooleanField(default=False, verbose_name="Подтверждено")
    week_number = models.PositiveSmallIntegerField(default=1, verbose_name="Номер недели")
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together     = ("teacher", "weekday", "slot_number")
        ordering            = ["weekday", "slot_number"]
        verbose_name        = "Запись расписания"
        verbose_name_plural = "Расписание"

    def __str__(self):
        return (
            f"{self.get_weekday_display()} пара {self.slot_number} — "
            f"{self.subject.name} ({self.teacher})"
        )


# ──────────────────────────────────────────────────────────────
#  TeacherPreference
# ──────────────────────────────────────────────────────────────

class TeacherPreference(models.Model):
    teacher = models.OneToOneField(
        User, on_delete=models.CASCADE,
        limit_choices_to={"is_teacher": True},
        related_name="preference", verbose_name="Преподаватель"
    )
    max_lessons_per_day      = models.PositiveSmallIntegerField(
        default=4, verbose_name="Макс. пар в день"
    )
    max_consecutive_lessons  = models.PositiveSmallIntegerField(
        default=2, verbose_name="Макс. пар подряд"
    )
    # [{"weekday": 0, "slot": 1}, ...]
    blocked_slots   = models.JSONField(default=list, blank=True, verbose_name="Заблокированные слоты")
    preferred_slots = models.JSONField(default=list, blank=True, verbose_name="Предпочтительные слоты")
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = "Пожелания преподавателя"
        verbose_name_plural = "Пожелания преподавателей"

    def __str__(self):
        return f"Пожелания: {self.teacher}"


# ──────────────────────────────────────────────────────────────
#  UniversitySettings  — настройки расписания
# ──────────────────────────────────────────────────────────────

class UniversitySettings(models.Model):
    university        = models.OneToOneField(
        University, on_delete=models.CASCADE, related_name="settings",
        verbose_name="Университет"
    )
    semester_weeks    = models.PositiveSmallIntegerField(
        default=18, verbose_name="Недель в семестре"
    )
    max_pairs_per_day = models.PositiveSmallIntegerField(
        default=6, verbose_name="Макс. пар в день"
    )
    # {"1":"08:30","2":"10:15","3":"12:00","4":"13:45","5":"15:30","6":"17:15"}
    slot_times        = models.JSONField(
        default=dict, blank=True,
        verbose_name="Времена пар",
        help_text='{"1":"08:30","2":"10:15","3":"12:00","4":"13:45","5":"15:30","6":"17:15"}'
    )
    # {"weight_no_gaps": 3000, ...}
    solver_weights    = models.JSONField(
        default=dict, blank=True,
        verbose_name="Веса солвера",
        help_text="Оставьте пустым для значений по умолчанию"
    )
    days              = models.JSONField(
        default=list, blank=True,
        verbose_name="Рабочие дни",
        help_text='["Пн","Вт","Ср","Чт","Пт","Сб"]'
    )

    class Meta:
        verbose_name        = "Настройки расписания"
        verbose_name_plural = "Настройки расписания"

    def __str__(self):
        return f"Настройки: {self.university.name}"

    def get_days(self):
        return self.days or ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]

    def get_slot_times(self):
        return self.slot_times or {
            "1": "08:30", "2": "10:15", "3": "12:00",
            "4": "13:45", "5": "15:30", "6": "17:15",
        }

    def get_solver_weights(self):
        defaults = {
            "weight_even_distribution":       10,
            "weight_prefer_morning":           5,
            "weight_no_gaps":               3000,
            "weight_room_stickiness":         15,
            "weight_single_pair_penalty":   5000,
            "weight_max_same_subject_per_day": 60,
            "weight_teacher_preferred":     8000,
            "weight_lecture_before_seminar": 500,
        }
        defaults.update(self.solver_weights or {})
        return defaults


# ──────────────────────────────────────────────────────────────
#  SemesterState  — прогресс генерации
# ──────────────────────────────────────────────────────────────

class SemesterState(models.Model):
    university   = models.ForeignKey(
        University, on_delete=models.CASCADE, related_name="semester_states",
        verbose_name="Университет"
    )
    current_week = models.PositiveSmallIntegerField(default=0, verbose_name="Текущая неделя")
    generated_at = models.DateTimeField(null=True, blank=True, verbose_name="Последняя генерация")
    # {"subj1__lec": 14, "subj1__sem__g1": 12, ...}
    remaining    = models.JSONField(default=dict, verbose_name="Остаток пар")

    class Meta:
        verbose_name        = "Состояние семестра"
        verbose_name_plural = "Состояния семестра"

    def __str__(self):
        return f"Семестр {self.university.name} — неделя {self.current_week}"