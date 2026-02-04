"""
Custom exceptions для Multi-Agent системы.
"""


class MessageBusError(Exception):
    """Базовая ошибка Message Bus."""
    pass


class MessageDeliveryError(MessageBusError):
    """Ошибка доставки сообщения."""
    pass


class TimeoutError(MessageBusError):
    """Таймаут ожидания ответа."""
    pass


class AgentNotFoundError(MessageBusError):
    """Агент не найден."""
    pass


class ValidationError(MessageBusError):
    """Ошибка валидации сообщения."""
    pass


class RetryExhaustedError(MessageBusError):
    """Исчерпаны все попытки retry."""
    pass
