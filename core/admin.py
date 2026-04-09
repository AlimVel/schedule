from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import (
    University, User, InviteLink,
    Direction, Course, Group,
    Classroom, Subject, SubjectConfig,
    ScheduleEntry, TeacherPreference,
    UniversitySettings, SemesterState,
)


# ──────────────────────────────────────────────────────────────
#  University
# ──────────────────────────────────────────────────────────────

@admin.register(University)
class UniversityAdmin(admin.ModelAdmin):
    list_display  = ("name", "created_at")
    search_fields = ("name",)


# ──────────────────────────────────────────────────────────────
#  User
# ──────────────────────────────────────────────────────────────

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Дополнительно", {
            "fields": ("university", "is_admin", "is_teacher", "middle_name", "academic_title")
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Дополнительно", {
            "fields": ("university", "is_admin", "is_teacher", "middle_name", "academic_title")
        }),
    )
    list_display  = ("username", "get_full_name", "is_teacher", "is_admin", "university", "academic_title")
    list_filter   = ("is_teacher", "is_admin", "university")
    search_fields = ("username", "first_name", "last_name", "email")
    list_select_related = ("university",)


# ──────────────────────────────────────────────────────────────
#  InviteLink
# ──────────────────────────────────────────────────────────────

@admin.register(InviteLink)
class InviteLinkAdmin(admin.ModelAdmin):
    list_display  = ("university", "token", "is_active", "created_at")
    list_filter   = ("is_active", "university")
    readonly_fields = ("token", "created_at")


# ──────────────────────────────────────────────────────────────
#  Direction / Course / Group
# ──────────────────────────────────────────────────────────────

class CourseInline(admin.TabularInline):
    model  = Course
    extra  = 1
    fields = ("number",)


@admin.register(Direction)
class DirectionAdmin(admin.ModelAdmin):
    list_display  = ("name", "university")
    list_filter   = ("university",)
    search_fields = ("name",)
    inlines       = [CourseInline]


class GroupInline(admin.TabularInline):
    model  = Group
    extra  = 1
    fields = ("name", "students")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display  = ("__str__", "direction", "number")
    list_filter   = ("direction__university", "direction")
    inlines       = [GroupInline]


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display  = ("name", "course", "students")
    list_filter   = ("course__direction__university", "course__direction")
    search_fields = ("name",)
    list_select_related = ("course__direction",)


# ──────────────────────────────────────────────────────────────
#  Classroom
# ──────────────────────────────────────────────────────────────

@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    list_display  = ("name", "university", "room_type_badge", "capacity", "low_priority")
    list_filter   = ("university", "room_type", "low_priority")
    search_fields = ("name",)
    list_editable = ("low_priority",)

    @admin.display(description="Тип")
    def room_type_badge(self, obj):
        colors = {
            "lecture": "#5A3FFF",
            "seminar": "#00A354",
            "comp":    "#0084FF",
            "special": "#FF6B00",
        }
        color = colors.get(obj.room_type, "#888")
        return format_html(
            '<span style="background:{}20;color:{};padding:2px 8px;border-radius:999px;font-size:12px;font-weight:700;">{}</span>',
            color, color, obj.get_room_type_display()
        )


# ──────────────────────────────────────────────────────────────
#  Subject + SubjectConfig
# ──────────────────────────────────────────────────────────────

class SubjectConfigInline(admin.TabularInline):
    model               = SubjectConfig
    extra               = 1
    fields              = ("kind", "teacher", "room_type", "total_pairs", "per_group", "subgroup_id")
    filter_horizontal   = ()
    show_change_link    = True
    verbose_name        = "Конфигурация занятия"
    verbose_name_plural = "Конфигурации занятий"


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display  = ("name", "university", "teacher", "difficulty_points", "hours_per_semester", "config_count")
    list_filter   = ("university", "difficulty_points")
    search_fields = ("name",)
    list_select_related = ("university", "teacher")
    inlines       = [SubjectConfigInline]

    @admin.display(description="Конфигов")
    def config_count(self, obj):
        n = obj.configs.count()
        color = "#00A354" if n > 0 else "#FF2D55"
        return format_html(
            '<span style="color:{};font-weight:700;">{}</span>', color, n
        )


@admin.register(SubjectConfig)
class SubjectConfigAdmin(admin.ModelAdmin):
    list_display        = ("subject", "kind_badge", "teacher", "room_type", "total_pairs", "per_group", "simultaneous", "group_list")
    list_filter         = ("kind", "room_type", "per_group", "simultaneous", "subject__university")
    search_fields       = ("subject__name", "teacher__last_name")
    filter_horizontal   = ("groups",)
    list_select_related = ("subject", "teacher")
    autocomplete_fields = ("subject", "teacher")

    fieldsets = (
        ("Основное", {
            "fields": ("subject", "kind", "teacher")
        }),
        ("Аудитория", {
            "fields": ("room_type", "fixed_room")
        }),
        ("Нагрузка", {
            "fields": ("total_pairs", "per_group", "simultaneous", "subgroup_id")
        }),
        ("Группы", {
            "fields": ("groups",)
        }),
        ("Порядок (лекция → семинар)", {
            "fields": ("min_lectures_before_seminars", "lecture_to_seminar_ratio"),
            "classes": ("collapse",),
        }),
    )

    @admin.display(description="Вид")
    def kind_badge(self, obj):
        colors = {"lecture": "#5A3FFF", "seminar": "#FF6B00", "comp": "#0084FF"}
        color  = colors.get(obj.kind, "#888")
        return format_html(
            '<span style="background:{}20;color:{};padding:2px 8px;border-radius:999px;font-size:12px;font-weight:700;">{}</span>',
            color, color, obj.get_kind_display()
        )

    @admin.display(description="Группы")
    def group_list(self, obj):
        groups = obj.groups.all()[:4]
        names  = ", ".join(g.name for g in groups)
        total  = obj.groups.count()
        if total > 4:
            names += f" +{total - 4}"
        return names or "—"


# ──────────────────────────────────────────────────────────────
#  ScheduleEntry
# ──────────────────────────────────────────────────────────────

@admin.register(ScheduleEntry)
class ScheduleEntryAdmin(admin.ModelAdmin):
    list_display  = ("weekday_name", "slot_number", "subject", "teacher", "classroom", "lesson_type_badge", "is_approved", "group_list")
    list_filter   = ("university", "weekday", "lesson_type", "is_approved")
    search_fields = ("subject__name", "teacher__last_name")
    list_editable = ("is_approved",)
    list_select_related = ("subject", "teacher", "classroom", "university")
    filter_horizontal   = ("groups",)

    @admin.display(description="День", ordering="weekday")
    def weekday_name(self, obj):
        return obj.get_weekday_display()

    @admin.display(description="Тип")
    def lesson_type_badge(self, obj):
        colors = {
            "lecture":  "#5A3FFF",
            "practice": "#FF2D55",
            "lab":      "#0084FF",
            "seminar":  "#FF6B00",
            "online":   "#00A354",
        }
        color = colors.get(obj.lesson_type, "#888")
        return format_html(
            '<span style="background:{}20;color:{};padding:2px 8px;border-radius:999px;font-size:12px;font-weight:700;">{}</span>',
            color, color, obj.get_lesson_type_display()
        )

    @admin.display(description="Группы")
    def group_list(self, obj):
        groups = obj.groups.all()[:3]
        names  = ", ".join(g.name for g in groups)
        total  = obj.groups.count()
        if total > 3:
            names += f" +{total - 3}"
        return names or "—"

    actions = ["approve_selected", "unapprove_selected"]

    @admin.action(description="Подтвердить выбранные")
    def approve_selected(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f"Подтверждено: {updated}")

    @admin.action(description="Снять подтверждение")
    def unapprove_selected(self, request, queryset):
        updated = queryset.update(is_approved=False)
        self.message_user(request, f"Снято подтверждение: {updated}")


# ──────────────────────────────────────────────────────────────
#  TeacherPreference
# ──────────────────────────────────────────────────────────────

@admin.register(TeacherPreference)
class TeacherPreferenceAdmin(admin.ModelAdmin):
    list_display  = ("teacher", "max_lessons_per_day", "max_consecutive_lessons", "blocked_count", "preferred_count", "updated_at")
    list_filter   = ("teacher__university",)
    search_fields = ("teacher__last_name", "teacher__username")
    readonly_fields = ("updated_at",)

    @admin.display(description="Заблок. слотов")
    def blocked_count(self, obj):
        n = len(obj.blocked_slots or [])
        return format_html('<span style="color:{};font-weight:700;">{}</span>',
                           "#FF2D55" if n else "#888", n)

    @admin.display(description="Предпочт. слотов")
    def preferred_count(self, obj):
        n = len(obj.preferred_slots or [])
        return format_html('<span style="color:{};font-weight:700;">{}</span>',
                           "#00A354" if n else "#888", n)


# ──────────────────────────────────────────────────────────────
#  UniversitySettings
# ──────────────────────────────────────────────────────────────

@admin.register(UniversitySettings)
class UniversitySettingsAdmin(admin.ModelAdmin):
    list_display = ("university", "semester_weeks", "max_pairs_per_day", "days_display")
    readonly_fields = ()

    fieldsets = (
        ("Основное", {
            "fields": ("university", "semester_weeks", "max_pairs_per_day", "days")
        }),
        ("Времена пар", {
            "fields": ("slot_times",),
            "description": 'JSON вида {"1":"08:30","2":"10:15","3":"12:00","4":"13:45","5":"15:30","6":"17:15"}',
        }),
        ("Веса солвера", {
            "fields": ("solver_weights",),
            "classes": ("collapse",),
            "description": "Оставьте пустым {} для значений по умолчанию",
        }),
    )

    @admin.display(description="Рабочие дни")
    def days_display(self, obj):
        days = obj.get_days()
        return " / ".join(days)


# ──────────────────────────────────────────────────────────────
#  SemesterState
# ──────────────────────────────────────────────────────────────

@admin.register(SemesterState)
class SemesterStateAdmin(admin.ModelAdmin):
    list_display  = ("university", "current_week", "generated_at", "remaining_pairs_total")
    list_filter   = ("university",)
    readonly_fields = ("generated_at", "remaining")

    @admin.display(description="Остаток пар (всего)")
    def remaining_pairs_total(self, obj):
        total = sum(obj.remaining.values()) if obj.remaining else 0
        return format_html('<span style="font-weight:700;">{}</span>', total)

    actions = ["reset_state"]

    @admin.action(description="Сбросить состояние семестра")
    def reset_state(self, request, queryset):
        for obj in queryset:
            obj.remaining    = {}
            obj.current_week = 0
            obj.generated_at = None
            obj.save()
        self.message_user(request, f"Сброшено: {queryset.count()}")