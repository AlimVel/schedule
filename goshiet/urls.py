from django.urls import path
from core import views

urlpatterns = [
    # ── Публичные страницы ──────────────────────────────────
    path('', views.index, name='index'),
    path('auth/', views.auth_view, name='auth'),
    path('logout/', views.logout_view, name='logout'),
    path('schedule/', views.schedule, name='schedule'),

    # ── Инвайт-система ──────────────────────────────────────
    path('generate-invite/', views.generate_invite, name='generate_invite'),
    path('invite/<uuid:token>/', views.teacher_register, name='teacher_register'),

    # ── Дашборды ────────────────────────────────────────────
    path('dashboard/', views.dashboard, name='dashboard'),
    path('teacher-dashboard/', views.teacher_dashboard, name='teacher_dashboard'),

    # ── Пожелания преподавателя ─────────────────────────────
    path('api/preferences/', views.save_preferences, name='save_preferences'),

    # ── Admin API — Предметы ─────────────────────────────────
    path('api/subjects/', views.subjects_api, name='subjects_api'),
    path('api/subjects/<int:pk>/', views.subject_detail, name='subject_detail'),

    # ── Admin API — Аудитории ────────────────────────────────
    path('api/classrooms/', views.classrooms_api, name='classrooms_api'),
    path('api/classrooms/<int:pk>/', views.classroom_detail, name='classroom_detail'),

    # ── Admin API — Структура университета ───────────────────
    path('api/directions/', views.directions_api, name='directions_api'),
    path('api/directions/<int:pk>/', views.direction_detail, name='direction_detail'),
    path('api/directions/<int:direction_id>/courses/', views.courses_api, name='courses_api'),
    path('api/courses/<int:pk>/', views.course_detail, name='course_detail'),
    path('api/courses/<int:course_id>/groups/', views.groups_api, name='groups_api'),
    path('api/groups/<int:pk>/', views.group_detail, name='group_detail'),

    # ── Admin API — Список + детали преподавателей ────────────
    path('api/teachers/', views.teachers_list, name='teachers_list'),
    path('api/teachers/<int:pk>/', views.teacher_detail_api, name='teacher_detail_api'),

    # ── Страница управления преподавателем (от имени админа) ──
    path('admin/teacher/<int:pk>/', views.admin_teacher_view, name='admin_teacher_view'),
    # ── Страница информации о базе данных ───────────────────────
    path('dbinfo/', views.dbinfo, name='dbinfo'),

    path('api/public/universities/', views.public_universities, name='public_universities'),
    path('api/public/directions/',   views.public_directions,   name='public_directions'),
    path('api/public/courses/',      views.public_courses,      name='public_courses'),
    path('api/public/groups/',       views.public_groups,       name='public_groups'),
    path('api/public/teachers/',     views.public_teachers,     name='public_teachers'),
    path('api/public/classrooms/',   views.public_classrooms,   name='public_classrooms'),
    path('api/public/schedule/',     views.public_schedule,     name='public_schedule'),

    path('api/subject-configs/',         views.subject_configs_api,    name='subject_configs'),
    path('api/subject-configs/<int:pk>/',views.subject_config_detail,  name='subject_config_detail'),
    path('api/schedule/generate/',       views.generate_schedule_api,  name='generate_schedule'),
    path('api/schedule/status/',         views.generation_status_api,  name='generation_status'),
    path('api/schedule/clear/',          views.clear_schedule_api,     name='clear_schedule'),
    path('api/schedule/reset-semester/', views.reset_semester_api,     name='reset_semester'),
]