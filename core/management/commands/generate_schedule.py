"""
core/management/commands/generate_schedule.py

Запуск:
  python manage.py generate_schedule --university 1
  python manage.py generate_schedule --university 1 --week 3
  python manage.py generate_schedule --university 1 --reset
"""
import sys
import time
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = 'Генерирует расписание для университета на основе данных из БД'

    def add_arguments(self, parser):
        parser.add_argument('--university', type=int, required=True,
                            help='ID университета')
        parser.add_argument('--week', type=int, default=None,
                            help='Номер недели (по умолчанию — следующая после текущей)')
        parser.add_argument('--weeks', type=int, default=1,
                            help='Сколько недель генерировать')
        parser.add_argument('--reset', action='store_true',
                            help='Сбросить состояние семестра перед генерацией')

    def handle(self, *args, **options):
        from core.models import University
        from core.scheduler.db_adapter import (
            build_input_from_db, load_state_from_db,
            save_state_to_db, save_schedule_to_db, reset_state,
        )

        # Импортируем алгоритм
        try:
            from algorithm.main import Model, GreedySolver, verify, print_summary
        except ImportError:
            raise CommandError(
                'Не найден модуль algorithm.main. '
                'Убедитесь что папка algorithm/ находится в PYTHONPATH '
                'или в корне проекта Django.'
            )

        try:
            university = University.objects.get(pk=options['university'])
        except University.DoesNotExist:
            raise CommandError(f"Университет с id={options['university']} не найден")

        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(f"  Университет: {university.name}")
        self.stdout.write(f"{'='*60}\n")

        if options['reset']:
            reset_state(university)
            self.stdout.write(self.style.WARNING('  Состояние семестра сброшено'))

        # Строим inp из БД
        self.stdout.write('  Загрузка данных из БД...')
        inp = build_input_from_db(university)

        n_rooms    = len(inp['rooms'])
        n_groups   = len(inp['groups'])
        n_teachers = len(inp['teachers'])
        n_subjects = len(inp['subjects'])
        self.stdout.write(f"  Аудиторий: {n_rooms} | Групп: {n_groups} | "
                          f"Преподавателей: {n_teachers} | Предметов: {n_subjects}")

        if not n_rooms:
            raise CommandError('Нет аудиторий — добавьте аудитории в систему')
        if not n_subjects:
            raise CommandError('Нет предметов с конфигурацией — добавьте SubjectConfig')

        # Загружаем state
        state = load_state_from_db(university, inp)
        sw    = inp['settings'].get('semester_weeks', 18)

        start_week = options['week'] or (state['current_week'] + 1)
        num_weeks  = options['weeks']

        total_placed = 0
        total_events = 0

        for w_offset in range(num_weeks):
            wn = start_week + w_offset
            if wn > sw:
                self.stdout.write(self.style.WARNING(f'  Неделя {wn} > {sw}, остановка'))
                break

            self.stdout.write(f"\n{'▓'*50}")
            self.stdout.write(f"  НЕДЕЛЯ {wn} / {sw}")
            self.stdout.write(f"{'▓'*50}")

            t0 = time.time()

            # Создаём модель
            model = Model(inp, state, wn)
            if not model.events:
                self.stdout.write('  Нет событий для этой недели')
                break

            total_events += len(model.events)

            # Запускаем солвер
            solver = GreedySolver(model)
            ok = solver.solve()

            # Верификация
            verify(model, solver)
            print_summary(model, solver, wn)

            # Сохраняем результат в БД
            with transaction.atomic():
                n_saved = save_schedule_to_db(university, model, solver, wn)
                # Обновляем state
                for e in model.events:
                    key = e.get('state_key')
                    if key and key in state['remaining']:
                        state['remaining'][key] = max(0, state['remaining'][key] - 1)
                state['current_week'] = wn
                save_state_to_db(university, state)

            total_placed += n_saved
            elapsed = time.time() - t0
            self.stdout.write(
                self.style.SUCCESS(f"  ✅ Сохранено в БД: {n_saved} записей ({elapsed:.2f}s)")
            )

        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(self.style.SUCCESS(
            f"  Итого: {total_placed} занятий сохранено | "
            f"{total_events} событий обработано"
        ))
        self.stdout.write(f"{'='*60}\n")