"""
core/scheduler/db_adapter.py

Адаптер: читает данные из БД и формирует структуру inp/state
для алгоритма (main.py), а также сохраняет результат обратно в БД.
"""
from collections import defaultdict
from django.utils import timezone


# ──────────────────────────────────────────────────────────────
#  BUILD INPUT  (БД → dict для алгоритма)
# ──────────────────────────────────────────────────────────────

def build_input_from_db(university):
    """
    Собирает полный inp-словарь из БД для указанного университета.
    Возвращает dict совместимый с Model(inp, state, week_num).
    """
    from core.models import (
        UniversitySettings, Classroom, Group, User,
        Subject, SubjectConfig, TeacherPreference,
    )

    # ── settings ──────────────────────────────────────────────
    try:
        us = university.settings
    except UniversitySettings.DoesNotExist:
        us = UniversitySettings.objects.create(university=university)

    settings = {
        "days":             us.get_days(),
        "max_pairs_per_day": us.max_pairs_per_day,
        "slot_times":       us.get_slot_times(),
        "solver":           us.get_solver_weights(),
        "semester_weeks":   us.semester_weeks,
    }

    # ── rooms ──────────────────────────────────────────────────
    rooms = []
    for c in Classroom.objects.filter(university=university):
        rooms.append({
            "id":           str(c.id),
            "capacity":     c.capacity,
            "type":         getattr(c, 'room_type', 'seminar'),
            "low_priority": getattr(c, 'low_priority', False),
        })

    # ── groups ─────────────────────────────────────────────────
    groups = []
    for g in Group.objects.filter(course__direction__university=university).select_related('course__direction'):
        groups.append({
            "id":       str(g.id),
            "name":     g.name,
            "students": getattr(g, 'students', 25),
            "course_id": g.course_id,
        })

    # ── teachers ──────────────────────────────────────────────
    teachers = []
    for t in User.objects.filter(university=university, is_teacher=True):
        pref_obj = getattr(t, 'preference', None)

        unavailable = []
        preferred   = []
        days_list   = settings["days"]

        if pref_obj:
            # blocked_slots: [{"weekday": 0, "slot": 1}, ...]
            for bs in (pref_obj.blocked_slots or []):
                wd = bs.get('weekday', 0)
                sl = bs.get('slot', 1)
                if 0 <= wd < len(days_list):
                    unavailable.append({"day": days_list[wd], "slots": [sl]})

            for ps in (pref_obj.preferred_slots or []):
                wd = ps.get('weekday', 0)
                sl = ps.get('slot', 1)
                if 0 <= wd < len(days_list):
                    preferred.append({"day": days_list[wd], "slots": [sl]})

        teachers.append({
            "id":               str(t.id),
            "name":             t.get_full_name() or t.username,
            "max_pairs_per_day": (pref_obj.max_lessons_per_day if pref_obj else 6),
            "unavailable":      unavailable,
            "preferred":        preferred,
        })

    # ── subjects ──────────────────────────────────────────────
    subjects = _build_subjects(university, settings["days"])

    return {
        "settings": settings,
        "rooms":    rooms,
        "groups":   groups,
        "teachers": teachers,
        "subjects": subjects,
    }


def _build_subjects(university, days_list):
    """
    Строит список subjects из SubjectConfig.
    Группирует конфиги по предмету: лекционные → lecture{},
    семинарные (per_group=True или subgroup_id) → seminar{}.
    """
    from core.models import SubjectConfig

    # Все конфиги для этого университета
    configs = (SubjectConfig.objects
               .filter(subject__university=university)
               .prefetch_related('groups', 'fixed_room')
               .select_related('subject', 'teacher'))

    # Группируем по предмету
    by_subject = defaultdict(list)
    for cfg in configs:
        by_subject[cfg.subject].append(cfg)

    subjects_out = []
    for subj, cfgs in by_subject.items():
        lec_cfgs = [c for c in cfgs if c.kind == SubjectConfig.KIND_LECTURE]
        sem_cfgs = [c for c in cfgs if c.kind in (SubjectConfig.KIND_SEMINAR, SubjectConfig.KIND_COMP)]

        # Список групп предмета (все группы из всех конфигов)
        all_group_ids = set()
        for c in cfgs:
            for g in c.groups.all():
                all_group_ids.add(str(g.id))

        s = {
            "id":     str(subj.id),
            "name":   subj.name,
            "groups": list(all_group_ids),
        }

        # lecture block
        if lec_cfgs:
            lc = lec_cfgs[0]
            s["lecture"] = {
                "teacher":    str(lc.teacher_id) if lc.teacher_id else "",
                "total_pairs": lc.total_pairs,
                "room_type":  lc.room_type,
            }
            if lc.fixed_room_id:
                s["lecture"]["fixed_room"] = str(lc.fixed_room_id)

        # seminar block
        if sem_cfgs:
            sc0 = sem_cfgs[0]
            sem_block = {
                "type":      sc0.kind,
                "room_type": sc0.room_type,
                "total_pairs_per_group": sc0.total_pairs,
            }

            # подгруппы (simultaneous или несколько конфигов семинара)
            if len(sem_cfgs) > 1 or sc0.subgroup_id:
                subgroups = []
                for sc in sem_cfgs:
                    sg_groups = [str(g.id) for g in sc.groups.all()]
                    subgroups.append({
                        "id":      sc.subgroup_id or f"sg_{sc.id}",
                        "teacher": str(sc.teacher_id) if sc.teacher_id else "",
                        "groups":  sg_groups,
                        "total_pairs_per_group": sc.total_pairs,
                    })
                sem_block["subgroups"]    = subgroups
                sem_block["simultaneous"] = sc0.simultaneous
            elif sc0.per_group:
                sem_block["per_group"]    = True
                sem_block["teacher"]      = str(sc0.teacher_id) if sc0.teacher_id else ""
                sem_block["total_pairs_per_group"] = sc0.total_pairs
            else:
                sem_block["teacher"]      = str(sc0.teacher_id) if sc0.teacher_id else ""

            # ordering
            if lec_cfgs and (sc0.min_lectures_before_seminars or sc0.lecture_to_seminar_ratio != 0.5):
                sem_block["ordering"] = {
                    "min_lectures_before_seminars_start": sc0.min_lectures_before_seminars,
                    "lecture_to_seminar_ratio": sc0.lecture_to_seminar_ratio,
                }

            s["seminar"] = sem_block

        subjects_out.append(s)

    return subjects_out


# ──────────────────────────────────────────────────────────────
#  BUILD STATE  (БД → state dict)
# ──────────────────────────────────────────────────────────────

def load_state_from_db(university, inp):
    """
    Загружает SemesterState из БД.
    Если не существует — инициализирует из inp.
    """
    from core.models import SemesterState

    obj, created = SemesterState.objects.get_or_create(
        university=university,
        defaults={"remaining": {}, "current_week": 0}
    )

    if created or not obj.remaining:
        obj.remaining = _init_remaining(inp)
        obj.save()

    return {
        "generated_at":  obj.generated_at.isoformat() if obj.generated_at else None,
        "semester_weeks": inp["settings"].get("semester_weeks", 18),
        "current_week":  obj.current_week,
        "remaining":     obj.remaining,
        "history":       [],
    }


def _init_remaining(inp):
    """Инициализирует remaining из inp (как в оригинальном init_state)."""
    rem = {}
    for subj in inp["subjects"]:
        sid = subj["id"]
        if subj.get("lecture"):
            rem[f"{sid}__lec"] = subj["lecture"]["total_pairs"]
        if subj.get("seminar"):
            sem = subj["seminar"]
            if sem.get("subgroups"):
                for sg in sem["subgroups"]:
                    rem[f"{sid}__sem__{sg['id']}"] = sem.get("total_pairs_per_group", 36)
            elif sem.get("per_group"):
                for g in subj["groups"]:
                    rem[f"{sid}__sem__{g}"] = sem["total_pairs_per_group"]
            else:
                rem[f"{sid}__sem"] = sem.get("total_pairs_per_group", 36)
    return rem


def save_state_to_db(university, state):
    """Сохраняет обновлённый state обратно в БД."""
    from core.models import SemesterState

    obj, _ = SemesterState.objects.get_or_create(university=university)
    obj.current_week = state["current_week"]
    obj.remaining    = state["remaining"]
    obj.generated_at = timezone.now()
    obj.save()


def reset_state(university):
    """Сбросить состояние семестра (начать заново)."""
    from core.models import SemesterState
    SemesterState.objects.filter(university=university).delete()


# ──────────────────────────────────────────────────────────────
#  SAVE RESULT  (результат алгоритма → ScheduleEntry в БД)
# ──────────────────────────────────────────────────────────────

def save_schedule_to_db(university, model, solver, week_num):
    from core.models import ScheduleEntry, Subject, Classroom, User, Group

    days_list = model.inp["settings"]["days"]
    NS = model.NS

    ScheduleEntry.objects.filter(university=university, week_number=week_num).delete()

    entries_to_create = []
    m2m_data = []

    for event in model.events:
        if solver.asgn[event["id"]] is None:
            continue

        ts, room_idx = solver.asgn[event["id"]]
        weekday = ts // NS
        slot_num = (ts % NS) + 1

        try:
            subject = Subject.objects.get(pk=int(event["subject_id"]))
        except (Subject.DoesNotExist, ValueError):
            continue

        try:
            teacher = User.objects.get(pk=int(event["teacher"]))
        except (User.DoesNotExist, ValueError):
            continue

        room_db_id = model.room_ids[room_idx]
        try:
            classroom = Classroom.objects.get(pk=int(room_db_id))
        except (Classroom.DoesNotExist, ValueError):
            classroom = None

        kind_map = {
            "lecture": "lecture",
            "seminar": "seminar",
            "comp": "lab",
        }
        lesson_type = kind_map.get(event["kind"], "lecture")

        entry = ScheduleEntry(
            university=university,
            subject=subject,
            teacher=teacher,
            classroom=classroom,
            weekday=weekday,
            slot_number=slot_num,
            lesson_type=lesson_type,
            is_approved=False,
            week_number=week_num
        )
        entries_to_create.append(entry)
        m2m_data.append(event["groups"])

    created = ScheduleEntry.objects.bulk_create(entries_to_create)

    for entry, group_ids in zip(created, m2m_data):
        db_ids = []
        for gid in group_ids:
            try:
                db_ids.append(int(gid))
            except ValueError:
                pass
        if db_ids:
            groups = Group.objects.filter(pk__in=db_ids)
            entry.groups.set(groups)

    return len(created)