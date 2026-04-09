import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt   # используем только там, где нет формы

from .models import (
    InviteLink, User, University,
    Direction, Course, Classroom, Subject,
    ScheduleEntry, TeacherPreference,
)


# ──────────────────────────────────────────────────────────────
#  Вспомогательные декораторы
# ──────────────────────────────────────────────────────────────

def admin_required(view_func):
    """Пускает только авторизованных администраторов."""
    @login_required(login_url='auth')
    def wrapper(request, *args, **kwargs):
        if not request.user.is_admin:
            return HttpResponse("Доступ запрещён.", status=403)
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def teacher_required(view_func):
    """Пускает только авторизованных преподавателей."""
    @login_required(login_url='auth')
    def wrapper(request, *args, **kwargs):
        if not request.user.is_teacher:
            return HttpResponse("Доступ запрещён.", status=403)
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def _json_body(request):
    """Парсит JSON-тело запроса, возвращает dict или пустой dict."""
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return {}


# ──────────────────────────────────────────────────────────────
#  Публичные страницы
# ──────────────────────────────────────────────────────────────

def index(request):
    return render(request, 'index.html')


def auth_view(request):
    if request.user.is_authenticated:
        if request.user.is_admin:
            return redirect('dashboard')
        elif request.user.is_teacher:
            return redirect('teacher_dashboard')

    context = {}
    if request.method == 'POST':
        user = authenticate(
            request,
            username=request.POST.get('username'),
            password=request.POST.get('password'),
        )
        if user is not None:
            login(request, user)
            if user.is_admin:
                return redirect('dashboard')
            elif user.is_teacher:
                return redirect('teacher_dashboard')
            return redirect('index')
        context['error'] = 'Неверный логин или пароль'

    return render(request, 'auth.html', context)


def logout_view(request):
    logout(request)
    return redirect('index')

def schedule(request):
    return render(request, 'schedule.html')


# ──────────────────────────────────────────────────────────────
#  Инвайт-система
# ──────────────────────────────────────────────────────────────

@admin_required
def generate_invite(request):
    if not request.user.university:
        return HttpResponse("Университет не привязан к аккаунту.", status=400)

    invite = InviteLink.objects.create(university=request.user.university)
    invite_url = request.build_absolute_uri(
        reverse('teacher_register', kwargs={'token': invite.token})
    )
    return render(request, 'invite_success.html', {
        'invite_url': invite_url,
        'university': request.user.university,
    })


def teacher_register(request, token):
    invite = get_object_or_404(InviteLink, token=token, is_active=True)
    university = invite.university
    context = {'university': university}

    if request.method == 'POST':
        username = request.POST.get('username')
        if User.objects.filter(username=username).exists():
            context['error'] = 'Этот логин уже занят. Попробуйте другой.'
            return render(request, 'teacher_register.html', context)

        user = User.objects.create_user(
            username=username,
            password=request.POST.get('password'),
            email=request.POST.get('email', ''),
            first_name=request.POST.get('first_name', ''),
            last_name=request.POST.get('last_name', ''),
            university=university,
            is_teacher=True,
        )
        user.middle_name = request.POST.get('middle_name', '')
        user.academic_title = request.POST.get('academic_title', '')
        user.save()

        # Сразу создаём пустой профиль пожеланий
        TeacherPreference.objects.get_or_create(teacher=user)

        return redirect('auth')

    return render(request, 'teacher_register.html', context)


# ──────────────────────────────────────────────────────────────
#  Дашборд администратора
# ──────────────────────────────────────────────────────────────

@admin_required
def dashboard(request):
    uni = request.user.university
    context = {
        'university': uni,
        'teachers_count': User.objects.filter(university=uni, is_teacher=True).count(),
        'classrooms_count': Classroom.objects.filter(university=uni).count(),
        'subjects_count': Subject.objects.filter(university=uni).count(),
        'directions_count': Direction.objects.filter(university=uni).count(),
    }
    return render(request, 'dashboard.html', context)


# ──────────────────────────────────────────────────────────────
#  ADMIN API — Предметы
# ──────────────────────────────────────────────────────────────

@admin_required
@require_http_methods(['GET', 'POST'])
def subjects_api(request):
    uni = request.user.university

    if request.method == 'GET':
        subjects = Subject.objects.filter(university=uni).select_related('teacher', 'course')
        data = [
            {
                'id': s.id,
                'name': s.name,
                'teacher_id': s.teacher_id,
                'teacher_name': str(s.teacher) if s.teacher else None,
                'difficulty_points': s.difficulty_points,
                'hours_per_semester': s.hours_per_semester,
                'course_id': s.course_id,
            }
            for s in subjects
        ]
        return JsonResponse({'subjects': data})

    # POST — создать предмет
    body = _json_body(request)
    subject = Subject.objects.create(
        university=uni,
        name=body.get('name', ''),
        teacher_id=body.get('teacher_id') or None,
        difficulty_points=body.get('difficulty_points', 1),
        hours_per_semester=body.get('hours_per_semester', 36),
        course_id=body.get('course_id') or None,
    )
    return JsonResponse({'id': subject.id, 'name': subject.name}, status=201)


@admin_required
@require_http_methods(['GET', 'PUT', 'DELETE'])
def subject_detail(request, pk):
    uni = request.user.university
    subject = get_object_or_404(Subject, pk=pk, university=uni)

    if request.method == 'GET':
        return JsonResponse({
            'id': subject.id,
            'name': subject.name,
            'teacher_id': subject.teacher_id,
            'difficulty_points': subject.difficulty_points,
            'hours_per_semester': subject.hours_per_semester,
            'course_id': subject.course_id,
        })

    if request.method == 'PUT':
        body = _json_body(request)
        subject.name = body.get('name', subject.name)
        subject.teacher_id = body.get('teacher_id') or subject.teacher_id
        subject.difficulty_points = body.get('difficulty_points', subject.difficulty_points)
        subject.hours_per_semester = body.get('hours_per_semester', subject.hours_per_semester)
        subject.course_id = body.get('course_id') or subject.course_id
        subject.save()
        return JsonResponse({'status': 'updated'})

    # DELETE
    subject.delete()
    return JsonResponse({'status': 'deleted'})


# ──────────────────────────────────────────────────────────────
#  ADMIN API — Аудитории
# ──────────────────────────────────────────────────────────────

@admin_required
@require_http_methods(['GET', 'POST'])
def classrooms_api(request):
    uni = request.user.university

    if request.method == 'GET':
        data = [
            {'id': c.id, 'name': c.name, 'capacity': c.capacity}
            for c in Classroom.objects.filter(university=uni)
        ]
        return JsonResponse({'classrooms': data})

    body = _json_body(request)
    classroom = Classroom.objects.create(
        university=uni,
        name=body.get('name', ''),
        capacity=body.get('capacity', 30),
    )
    return JsonResponse({'id': classroom.id, 'name': classroom.name}, status=201)


@admin_required
@require_http_methods(['PUT', 'DELETE'])
def classroom_detail(request, pk):
    uni = request.user.university
    classroom = get_object_or_404(Classroom, pk=pk, university=uni)

    if request.method == 'PUT':
        body = _json_body(request)
        classroom.name = body.get('name', classroom.name)
        classroom.capacity = body.get('capacity', classroom.capacity)
        classroom.save()
        return JsonResponse({'status': 'updated'})

    classroom.delete()
    return JsonResponse({'status': 'deleted'})


# ──────────────────────────────────────────────────────────────
#  ADMIN API — Направления и курсы
# ──────────────────────────────────────────────────────────────

@admin_required
@require_http_methods(['GET', 'POST'])
def directions_api(request):
    uni = request.user.university

    if request.method == 'GET':
        data = [
            {'id': d.id, 'name': d.name}
            for d in Direction.objects.filter(university=uni)
        ]
        return JsonResponse({'directions': data})

    body = _json_body(request)
    direction = Direction.objects.create(university=uni, name=body.get('name', ''))
    return JsonResponse({'id': direction.id, 'name': direction.name}, status=201)


@admin_required
@require_http_methods(['GET', 'POST'])
def courses_api(request, direction_id):
    uni = request.user.university
    direction = get_object_or_404(Direction, pk=direction_id, university=uni)

    if request.method == 'GET':
        data = [
            {'id': c.id, 'number': c.number}
            for c in Course.objects.filter(direction=direction)
        ]
        return JsonResponse({'courses': data})

    body = _json_body(request)
    course, created = Course.objects.get_or_create(
        direction=direction,
        number=body.get('number', 1),
    )
    return JsonResponse({'id': course.id, 'number': course.number}, status=201 if created else 200)


# ──────────────────────────────────────────────────────────────
#  ADMIN API — Расписание
# ──────────────────────────────────────────────────────────────

@admin_required
@require_http_methods(['GET', 'POST'])
def schedule_api(request):
    uni = request.user.university

    if request.method == 'GET':
        qs = ScheduleEntry.objects.filter(university=uni).select_related(
            'subject', 'teacher', 'classroom', 'course__direction'
        )
        # Необязательные фильтры через query-params
        course_id = request.GET.get('course_id')
        teacher_id = request.GET.get('teacher_id')
        if course_id:
            qs = qs.filter(course_id=course_id)
        if teacher_id:
            qs = qs.filter(teacher_id=teacher_id)

        data = [
            {
                'id': e.id,
                'subject': e.subject.name,
                'teacher': str(e.teacher),
                'classroom': e.classroom.name if e.classroom else None,
                'course': str(e.course) if e.course else None,
                'weekday': e.weekday,
                'weekday_display': e.get_weekday_display(),
                'slot_number': e.slot_number,
                'lesson_type': e.lesson_type,
                'is_approved': e.is_approved,
            }
            for e in qs
        ]
        return JsonResponse({'entries': data})

    # POST — создать запись вручную
    body = _json_body(request)
    try:
        entry = ScheduleEntry.objects.create(
            university=uni,
            subject_id=body['subject_id'],
            teacher_id=body['teacher_id'],
            classroom_id=body.get('classroom_id'),
            course_id=body.get('course_id'),
            weekday=body['weekday'],
            slot_number=body['slot_number'],
            lesson_type=body.get('lesson_type', 'lecture'),
        )
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'id': entry.id}, status=201)


@admin_required
@require_http_methods(['GET', 'PUT', 'DELETE'])
def schedule_entry(request, pk):
    uni = request.user.university
    entry = get_object_or_404(ScheduleEntry, pk=pk, university=uni)

    if request.method == 'GET':
        return JsonResponse({
            'id': entry.id,
            'subject_id': entry.subject_id,
            'teacher_id': entry.teacher_id,
            'classroom_id': entry.classroom_id,
            'course_id': entry.course_id,
            'weekday': entry.weekday,
            'slot_number': entry.slot_number,
            'lesson_type': entry.lesson_type,
            'is_approved': entry.is_approved,
        })

    if request.method == 'PUT':
        body = _json_body(request)
        for field in ('subject_id', 'teacher_id', 'classroom_id', 'course_id',
                      'weekday', 'slot_number', 'lesson_type', 'is_approved'):
            if field in body:
                setattr(entry, field, body[field])
        try:
            entry.save()
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
        return JsonResponse({'status': 'updated'})

    entry.delete()
    return JsonResponse({'status': 'deleted'})


@admin_required
@require_http_methods(['POST'])
def approve_entry(request, pk):
    """Быстрое подтверждение одной записи расписания."""
    entry = get_object_or_404(ScheduleEntry, pk=pk, university=request.user.university)
    entry.is_approved = True
    entry.save(update_fields=['is_approved'])
    return JsonResponse({'status': 'approved', 'id': entry.id})


# ──────────────────────────────────────────────────────────────
#  Дашборд преподавателя
# ──────────────────────────────────────────────────────────────

@teacher_required
def teacher_dashboard(request):
    teacher = request.user
    pref, _ = TeacherPreference.objects.get_or_create(teacher=teacher)

    # Расписание этого преподавателя (для просмотра)
    my_schedule = (
        ScheduleEntry.objects
        .filter(teacher=teacher)
        .select_related('subject', 'classroom', 'course__direction')
        .order_by('weekday', 'slot_number')
    )

    context = {
        'pref': pref,
        'my_schedule': my_schedule,
    }
    return render(request, 'teacher_dashboard.html', context)


# ──────────────────────────────────────────────────────────────
#  Сохранение пожеланий преподавателя
# ──────────────────────────────────────────────────────────────

@teacher_required
@require_http_methods(['POST'])
def save_preferences(request):
    """
    Принимает JSON:
    {
      "max_lessons_per_day": 4,
      "max_consecutive_lessons": 2,
      "blocked_slots":   [{"weekday": 0, "slot": 1}, ...],
      "preferred_slots": [{"weekday": 2, "slot": 3}, ...]
    }
    Возвращает JSON {"status": "ok"}.
    """
    teacher = request.user
    body = _json_body(request)

    pref, _ = TeacherPreference.objects.get_or_create(teacher=teacher)
    pref.max_lessons_per_day = body.get('max_lessons_per_day', pref.max_lessons_per_day)
    pref.max_consecutive_lessons = body.get(
        'max_consecutive_lessons', pref.max_consecutive_lessons
    )
    pref.blocked_slots = body.get('blocked_slots', pref.blocked_slots)
    pref.preferred_slots = body.get('preferred_slots', pref.preferred_slots)
    pref.save()

    return JsonResponse({'status': 'ok'})


# ──────────────────────────────────────────────────────────────
#  API — список преподавателей (для выпадающих списков в формах)
# ──────────────────────────────────────────────────────────────

@admin_required
@require_http_methods(['GET'])
def teachers_list(request):
    uni = request.user.university
    teachers = User.objects.filter(university=uni, is_teacher=True)
    data = [
        {
            'id': t.id,
            'full_name': f"{t.last_name} {t.first_name} {t.middle_name or ''}".strip(),
            'academic_title': t.academic_title or '',
            'username': t.username,
            'email': t.email or '—',
        }
        for t in teachers
    ]
    return JsonResponse({'teachers': data})

# ──────────────────────────────────────────────────────────────
#  API — редактирование конкретного преподавателя (только для админа)
# ──────────────────────────────────────────────────────────────

@admin_required
@require_http_methods(['GET', 'PUT'])
def teacher_detail_api(request, pk):
    uni = request.user.university
    teacher = get_object_or_404(User, pk=pk, university=uni, is_teacher=True)

    if request.method == 'GET':
        pref = getattr(teacher, 'preference', None)
        return JsonResponse({
            'id': teacher.id,
            'username': teacher.username,
            'first_name': teacher.first_name,
            'last_name': teacher.last_name,
            'middle_name': teacher.middle_name or '',
            'email': teacher.email,
            'academic_title': teacher.academic_title or '',
            'max_lessons_per_day': pref.max_lessons_per_day if pref else 4,
            'max_consecutive_lessons': pref.max_consecutive_lessons if pref else 2,
            'blocked_slots': pref.blocked_slots if pref else [],
            'preferred_slots': pref.preferred_slots if pref else [],
        })

    body = _json_body(request)

    for field in ('first_name', 'last_name', 'middle_name', 'email', 'academic_title'):
        if field in body:
            setattr(teacher, field, body[field])

    new_password = body.get('new_password', '').strip()
    if new_password:
        teacher.set_password(new_password)

    teacher.save()

    pref_fields = ('max_lessons_per_day', 'max_consecutive_lessons', 'blocked_slots', 'preferred_slots')
    if any(f in body for f in pref_fields):
        pref, _ = TeacherPreference.objects.get_or_create(teacher=teacher)
        if 'max_lessons_per_day' in body:
            pref.max_lessons_per_day = body['max_lessons_per_day']
        if 'max_consecutive_lessons' in body:
            pref.max_consecutive_lessons = body['max_consecutive_lessons']
        if 'blocked_slots' in body:
            pref.blocked_slots = body['blocked_slots']
        if 'preferred_slots' in body:
            pref.preferred_slots = body['preferred_slots']
        pref.save()

    return JsonResponse({'status': 'updated'})


# ──────────────────────────────────────────────────────────────
#  Страница управления преподавателем (от имени администратора)
# ──────────────────────────────────────────────────────────────

@admin_required
def admin_teacher_view(request, pk):
    uni = request.user.university
    teacher = get_object_or_404(User, pk=pk, university=uni, is_teacher=True)
    pref, _ = TeacherPreference.objects.get_or_create(teacher=teacher)

    teacher_schedule = (
        ScheduleEntry.objects
        .filter(teacher=teacher)
        .select_related('subject', 'classroom', 'course__direction')
        .order_by('weekday', 'slot_number')
    )

    context = {
        'teacher': teacher,
        'pref': pref,
        'teacher_schedule': teacher_schedule,
        'university': uni,
    }
    return render(request, 'admin_teacher_view.html', context)

def dbinfo(request):
    return render(request, 'dbinfo.html')

# ──────────────────────────────────────────────────────────────
#  ADMIN API — Группы
# ──────────────────────────────────────────────────────────────

from .models import Group as StudentGroup   # псевдоним чтобы не конфликтовало

@admin_required
@require_http_methods(['GET', 'POST'])
def groups_api(request, course_id):
    """
    GET  /api/courses/<course_id>/groups/  — список групп курса
    POST /api/courses/<course_id>/groups/  — создать группу
    """
    uni = request.user.university
    # проверяем, что курс принадлежит университету
    from .models import Course as CourseModel
    course = get_object_or_404(
        CourseModel,
        pk=course_id,
        direction__university=uni,
    )

    if request.method == 'GET':
        data = [
            {'id': g.id, 'name': g.name, 'course_id': g.course_id}
            for g in StudentGroup.objects.filter(course=course)
        ]
        return JsonResponse({'groups': data})

    body = _json_body(request)
    name = body.get('name', '').strip()
    if not name:
        return JsonResponse({'error': 'Название обязательно'}, status=400)

    group, created = StudentGroup.objects.get_or_create(course=course, name=name)
    return JsonResponse({'id': group.id, 'name': group.name}, status=201 if created else 200)


@admin_required
@require_http_methods(['DELETE'])
def group_detail(request, pk):
    """DELETE /api/groups/<pk>/"""
    uni = request.user.university
    group = get_object_or_404(StudentGroup, pk=pk, course__direction__university=uni)
    group.delete()
    return JsonResponse({'status': 'deleted'})


@admin_required
@require_http_methods(['DELETE'])
def course_detail(request, pk):
    """DELETE /api/courses/<pk>/  — удалить курс (каскадно удаляются группы)"""
    uni = request.user.university
    from .models import Course as CourseModel
    course = get_object_or_404(CourseModel, pk=pk, direction__university=uni)
    course.delete()
    return JsonResponse({'status': 'deleted'})


@admin_required
@require_http_methods(['DELETE'])
def direction_detail(request, pk):
    """DELETE /api/directions/<pk>/  — удалить направление (каскадно)"""
    uni = request.user.university
    direction = get_object_or_404(Direction, pk=pk, university=uni)
    direction.delete()
    return JsonResponse({'status': 'deleted'})

@require_http_methods(['GET'])
def public_universities(request):
    from .models import University
    return JsonResponse({'universities': list(University.objects.values('id','name'))})
 
@require_http_methods(['GET'])
def public_directions(request):
    qs = Direction.objects.all()
    if uni := request.GET.get('university_id'):
        qs = qs.filter(university_id=uni)
    return JsonResponse({'directions': [{'id':d.id,'name':d.name} for d in qs]})
 
@require_http_methods(['GET'])
def public_courses(request):
    from .models import Course as CM
    qs = CM.objects.all()
    if did := request.GET.get('direction_id'):
        qs = qs.filter(direction_id=did)
    return JsonResponse({'courses': [{'id':c.id,'number':c.number} for c in qs.order_by('number')]})
 
@require_http_methods(['GET'])
def public_groups(request):
    from .models import Group as GM
    qs = GM.objects.all()
    if cid := request.GET.get('course_id'):
        qs = qs.filter(course_id=cid)
    return JsonResponse({'groups': [{'id':g.id,'name':g.name} for g in qs]})
 
@require_http_methods(['GET'])
def public_teachers(request):
    qs = User.objects.filter(is_teacher=True)
    if uni := request.GET.get('university_id'):
        qs = qs.filter(university_id=uni)
    return JsonResponse({'teachers': [
        {'id':t.id,'name':f"{t.last_name} {t.first_name} {t.middle_name or ''}".strip() or t.username}
        for t in qs
    ]})
 
@require_http_methods(['GET'])
def public_classrooms(request):
    qs = Classroom.objects.all()
    if uni := request.GET.get('university_id'):
        qs = qs.filter(university_id=uni)
    return JsonResponse({'classrooms': [{'id':c.id,'name':c.name} for c in qs]})
 
@require_http_methods(['GET'])
def public_schedule(request):
    SLOT_TIMES = {1:'08:30–10:05',2:'10:15–11:50',3:'12:00–13:35',
                  4:'13:45–15:20',5:'15:30–17:05',6:'17:15–18:50'}
    qs = ScheduleEntry.objects.select_related(
        'subject','teacher','classroom','course__direction__university'
    )
    if uni := request.GET.get('university_id'):   qs = qs.filter(university_id=uni)
    if did := request.GET.get('direction_id'):    qs = qs.filter(course__direction_id=did)
    if cid := request.GET.get('course_id'):       qs = qs.filter(course_id=cid)
    if tid := request.GET.get('teacher_id'):      qs = qs.filter(teacher_id=tid)
    if rid := request.GET.get('classroom_id'):    qs = qs.filter(classroom_id=rid)
    # group_id — фильтрация через Group→Course→ScheduleEntry
    if gid := request.GET.get('group_id'):
        from .models import Group as GM
        try:
            g = GM.objects.get(pk=gid)
            qs = qs.filter(course=g.course)
        except GM.DoesNotExist:
            qs = qs.none()
 
    return JsonResponse({'entries': [{
        'id':                  e.id,
        'weekday':             e.weekday,
        'slot':                e.slot_number,
        'slot_time':           SLOT_TIMES.get(e.slot_number,''),
        'subject':             e.subject.name,
        'teacher_id':          e.teacher_id,
        'teacher':             f"{e.teacher.last_name} {e.teacher.first_name}".strip() or e.teacher.username,
        'classroom':           e.classroom.name if e.classroom else '—',
        'lesson_type':         e.lesson_type,
        'lesson_type_display': e.get_lesson_type_display(),
        'is_approved':         e.is_approved,
    } for e in qs]})

@admin_required
@require_http_methods(['GET', 'POST'])
def subject_configs_api(request):
    uni = request.user.university
    from .models import SubjectConfig
 
    if request.method == 'GET':
        configs = (SubjectConfig.objects
                   .filter(subject__university=uni)
                   .select_related('subject', 'teacher', 'fixed_room')
                   .prefetch_related('groups'))
        data = [{
            'id':           c.id,
            'subject_id':   c.subject_id,
            'subject_name': c.subject.name,
            'kind':         c.kind,
            'room_type':    c.room_type,
            'teacher_id':   c.teacher_id,
            'teacher_name': str(c.teacher) if c.teacher else None,
            'total_pairs':  c.total_pairs,
            'per_group':    c.per_group,
            'simultaneous': c.simultaneous,
            'subgroup_id':  c.subgroup_id,
            'group_ids':    [g.id for g in c.groups.all()],
        } for c in configs]
        return JsonResponse({'configs': data})
 
    body = _json_body(request)
    from .models import SubjectConfig, Group as GroupModel
    cfg = SubjectConfig.objects.create(
        subject_id   = body['subject_id'],
        kind         = body.get('kind', 'lecture'),
        room_type    = body.get('room_type', 'seminar'),
        teacher_id   = body.get('teacher_id') or None,
        total_pairs  = body.get('total_pairs', 18),
        per_group    = body.get('per_group', False),
        simultaneous = body.get('simultaneous', False),
        subgroup_id  = body.get('subgroup_id', ''),
    )
    if body.get('group_ids'):
        cfg.groups.set(GroupModel.objects.filter(pk__in=body['group_ids']))
    return JsonResponse({'id': cfg.id}, status=201)
 
 
@admin_required
@require_http_methods(['PUT', 'DELETE'])
def subject_config_detail(request, pk):
    uni = request.user.university
    from .models import SubjectConfig, Group as GroupModel
    cfg = get_object_or_404(SubjectConfig, pk=pk, subject__university=uni)
 
    if request.method == 'DELETE':
        cfg.delete()
        return JsonResponse({'status': 'deleted'})
 
    body = _json_body(request)
    cfg.subject_id   = body.get('subject_id',  cfg.subject_id)
    cfg.kind         = body.get('kind',         cfg.kind)
    cfg.room_type    = body.get('room_type',    cfg.room_type)
    cfg.teacher_id   = body.get('teacher_id') or None
    cfg.total_pairs  = body.get('total_pairs',  cfg.total_pairs)
    cfg.per_group    = body.get('per_group',    cfg.per_group)
    cfg.simultaneous = body.get('simultaneous', cfg.simultaneous)
    cfg.subgroup_id  = body.get('subgroup_id',  cfg.subgroup_id)
    cfg.save()
    if 'group_ids' in body:
        cfg.groups.set(GroupModel.objects.filter(pk__in=body['group_ids']))
    return JsonResponse({'status': 'updated'})
 
 
# ──────────────────────────────────────────────────────────────
#  Generation API
# ──────────────────────────────────────────────────────────────
 
import threading
import traceback
 
_generation_status = {}
 
 
def _run_generation(university_id, week, weeks, reset):
    from core.models import University
    from core.scheduler.db_adapter import (
        build_input_from_db, load_state_from_db,
        save_state_to_db, save_schedule_to_db, reset_state,
    )
    from algorithm.main import Model, GreedySolver
    from django.db import transaction
 
    uid = university_id
    _generation_status[uid] = {'status': 'running', 'log': [], 'progress': 0}
 
    def log(msg):
        _generation_status[uid]['log'].append(msg)
 
    try:
        university = University.objects.get(pk=uid)
        log(f"Загрузка данных для «{university.name}»...")
 
        if reset:
            reset_state(university)
            log("Состояние семестра сброшено")
 
        inp   = build_input_from_db(university)
        state = load_state_from_db(university, inp)
        sw    = inp['settings'].get('semester_weeks', 18)
 
        log(f"Аудиторий: {len(inp['rooms'])} | Групп: {len(inp['groups'])} | "
            f"Преподавателей: {len(inp['teachers'])} | Предметов: {len(inp['subjects'])}")
 
        if not inp['rooms']:
            raise ValueError("Нет аудиторий в системе")
        if not inp['subjects']:
            raise ValueError("Нет предметов с конфигурацией (SubjectConfig)")
 
        start_week  = week or (state['current_week'] + 1)
        total_saved = 0
 
        for w_offset in range(weeks):
            wn = start_week + w_offset
            if wn > sw:
                log(f"Неделя {wn} > {sw}, остановка")
                break
 
            log(f"\n▶ Неделя {wn}/{sw}")
            _generation_status[uid]['progress'] = int((w_offset / weeks) * 100)
 
            model = Model(inp, state, wn)
            if not model.events:
                log("Нет событий для этой недели")
                break
 
            log(f"Событий: {len(model.events)}")
            solver = GreedySolver(model)
            solver.solve()
 
            with transaction.atomic():
                n_saved = save_schedule_to_db(university, model, solver, wn)
                for e in model.events:
                    key = e.get('state_key')
                    if key and key in state['remaining']:
                        state['remaining'][key] = max(0, state['remaining'][key] - 1)
                state['current_week'] = wn
                save_state_to_db(university, state)
 
            total_saved += n_saved
            log(f"✅ Сохранено {n_saved} занятий")
 
        _generation_status[uid] = {
            'status':       'done',
            'log':          _generation_status[uid]['log'],
            'progress':     100,
            'total':        total_saved,
            'week':         state['current_week'],
        }
 
    except Exception as exc:
        _generation_status[uid] = {
            'status': 'error',
            'log':    _generation_status[uid].get('log', []) + [f"ОШИБКА: {exc}"],
            'error':  traceback.format_exc(),
        }
 
 
@admin_required
@require_http_methods(['POST'])
def generate_schedule_api(request):
    uni = request.user.university
    if not uni:
        return JsonResponse({'error': 'Университет не привязан'}, status=400)
    body = _json_body(request)
    uid  = uni.id
    if _generation_status.get(uid, {}).get('status') == 'running':
        return JsonResponse({'error': 'Генерация уже выполняется'}, status=409)
    threading.Thread(
        target=_run_generation,
        args=(uid, body.get('week'), body.get('weeks', 1), body.get('reset', False)),
        daemon=True
    ).start()
    return JsonResponse({'status': 'started'})
 
 
@admin_required
@require_http_methods(['GET'])
def generation_status_api(request):
    uni = request.user.university
    if not uni:
        return JsonResponse({'status': 'idle'})
    status = dict(_generation_status.get(uni.id, {'status': 'idle'}))
    try:
        from core.models import SemesterState, ScheduleEntry, UniversitySettings
        obj = SemesterState.objects.filter(university=uni).first()
        status['current_week']  = obj.current_week if obj else 0
        status['generated_at']  = obj.generated_at.isoformat() if obj and obj.generated_at else None
        try:
            status['semester_weeks'] = uni.settings.semester_weeks
        except Exception:
            status['semester_weeks'] = 18
        status['entries_count'] = ScheduleEntry.objects.filter(university=uni).count()
    except Exception:
        pass
    return JsonResponse(status)
 
 
@admin_required
@require_http_methods(['DELETE'])
def clear_schedule_api(request):
    from core.models import ScheduleEntry
    n, _ = ScheduleEntry.objects.filter(university=request.user.university).delete()
    return JsonResponse({'deleted': n})
 
 
@admin_required
@require_http_methods(['POST'])
def reset_semester_api(request):
    from core.scheduler.db_adapter import reset_state
    reset_state(request.user.university)
    return JsonResponse({'status': 'reset'})
 