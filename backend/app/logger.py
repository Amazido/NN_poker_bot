"""Логирование через loguru с именованными логгерами."""
import sys

from loguru import logger

from app.config import LOG_LEVEL

# Один раз настраиваем sink на stdout.
logger.remove()
logger.add(
    sys.stdout,
    level=LOG_LEVEL,
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{extra[name]}</cyan> | "
        "<level>{message}</level>"
    ),
    colorize=True,
)


def get_logger(name: str):
    """Логгер с меткой компонента (name попадает в extra[name])."""
    return logger.bind(name=name)


# Часто используемые логгеры
startup_log = get_logger("STARTUP")
auth_log = get_logger("AUTH")
poker_log = get_logger("POKER")
task_log = get_logger("TASK")
