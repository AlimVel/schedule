"""
core/logger.py

Утилита логирования важных действий в GoShiet.
Пишет в logs/actions.log (рядом с manage.py).

Использование:
    from core.logger import log_action
    log_action(request, 'subject_created', f'Предмет «{subject.name}»')
"""

import logging
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR  = BASE_DIR / 'logs'
LOG_FILE = LOG_DIR / 'actions.log'

LOG_DIR.mkdir(exist_ok=True)


def _get_logger():
    logger = logging.getLogger('goshiet.actions')
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter(
        fmt='%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    ))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def log_action(request_or_user, action: str, detail: str = ''):
    """
    Записывает одну строку в logs/actions.log.

    :param request_or_user: HttpRequest или User
    :param action:  краткий код,   напр. 'subject_created'
    :param detail:  описание,      напр. 'Предмет «Матан»'
    """
    try:
        user = request_or_user.user
        ip   = (
            request_or_user.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
            or request_or_user.META.get('REMOTE_ADDR', '—')
        )
    except AttributeError:
        user = request_or_user
        ip   = '—'

    username = getattr(user, 'username', str(user)) if user else 'anonymous'
    uni_name = '—'
    try:
        uni_name = user.university.name if user and user.university else '—'
    except Exception:
        pass

    msg = (
        f"{action:<30} | "
        f"user={username:<20} | "
        f"uni={uni_name:<25} | "
        f"ip={ip:<15} | "
        f"{detail}"
    )
    _get_logger().info(msg)