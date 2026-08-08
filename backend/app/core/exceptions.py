"""Доменные исключения приложения."""


class AppError(Exception):
    """Базовая ошибка домена."""


class NotAuthenticated(AppError):
    """Пользователь не авторизован / токен невалиден."""


class InvalidCredentials(AppError):
    """Неверные учётные данные (например, подпись Telegram)."""


class NotFound(AppError):
    """Сущность не найдена."""


class Conflict(AppError):
    """Конфликт состояния (например, стол уже полон)."""


class InvalidMove(AppError):
    """Недопустимое игровое действие в текущем состоянии."""
