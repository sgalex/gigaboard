"""
Configuration для Multi-Agent системы: таймауты, retry, limits.
"""
from typing import Dict, Optional
from .message_types import MessageType


class TimeoutConfig:
    """
    Конфигурация таймаутов для различных типов сообщений и агентов.
    
    См. docs/MULTI_AGENT_SYSTEM.md для обоснования значений.
    """
    
    # Таймауты по типам сообщений (секунды)
    MESSAGE_TIMEOUTS: Dict[MessageType, int] = {
        MessageType.USER_REQUEST: 30,           # Простые запросы
        MessageType.TASK_REQUEST: 60,           # Делегирование задач
        MessageType.TASK_RESULT: 120,           # Результаты могут быть медленными
        MessageType.TASK_PROGRESS: 5,           # Прогресс должен быть быстрым
        MessageType.AGENT_QUERY: 10,            # Быстрые межагентные запросы
        MessageType.AGENT_RESPONSE: 10,
        MessageType.ACKNOWLEDGEMENT: 5,
        MessageType.ERROR: 5,
        MessageType.SUGGESTED_ACTIONS: 15,
        MessageType.NODE_CREATED: 5,
        MessageType.UI_NOTIFICATION: 5,
    }
    
    # Таймауты по агентам (секунды) - переопределяют MESSAGE_TIMEOUTS
    AGENT_TIMEOUTS: Dict[str, int] = {
        "planner": 30,          # Planner должен быть быстрым
        "researcher": 120,      # Researcher может делать медленные HTTP/SQL запросы
        "analyst": 60,          # Analyst анализирует данные
        "developer": 90,        # Developer генерирует код
        "reporter": 60,         # Reporter создаёт визуализации
        "transformation": 90,   # Transformation выполняет pandas операции
        "executor": 300,        # Executor может выполнять долгие задачи
        "form_generator": 30,
        "data_discovery": 120,
    }
    
    # Дефолтный таймаут если не указан
    DEFAULT_TIMEOUT: int = 60
    
    @classmethod
    def get_timeout(cls, message_type: MessageType, agent_name: Optional[str] = None) -> int:
        """
        Получить таймаут для сообщения.
        
        Приоритет:
        1. Таймаут агента (если указан)
        2. Таймаут типа сообщения
        3. Дефолтный таймаут
        
        Args:
            message_type: Тип сообщения
            agent_name: Имя агента (опционально)
            
        Returns:
            int: Таймаут в секундах
        """
        if agent_name and agent_name in cls.AGENT_TIMEOUTS:
            return cls.AGENT_TIMEOUTS[agent_name]
        
        return cls.MESSAGE_TIMEOUTS.get(message_type, cls.DEFAULT_TIMEOUT)


class RetryConfig:
    """
    Конфигурация retry логики для Message Bus.
    """
    
    # Максимальное количество повторов
    MAX_RETRIES: int = 3
    
    # Начальная задержка (секунды)
    INITIAL_BACKOFF: float = 1.0
    
    # Множитель для exponential backoff
    BACKOFF_FACTOR: float = 2.0
    
    # Максимальная задержка между попытками (секунды)
    MAX_BACKOFF: float = 30.0
    
    # Типы сообщений, для которых НЕ делаем retry
    NO_RETRY_MESSAGE_TYPES = {
        MessageType.ACKNOWLEDGEMENT,
        MessageType.TASK_PROGRESS,
        MessageType.UI_NOTIFICATION,
    }
    
    @classmethod
    def should_retry(cls, message_type: MessageType, retry_count: int) -> bool:
        """
        Проверить, нужно ли делать retry для сообщения.
        
        Args:
            message_type: Тип сообщения
            retry_count: Текущее количество повторов
            
        Returns:
            bool: True если нужно повторить
        """
        if message_type in cls.NO_RETRY_MESSAGE_TYPES:
            return False
        
        return retry_count < cls.MAX_RETRIES
    
    @classmethod
    def get_backoff_delay(cls, retry_count: int) -> float:
        """
        Рассчитать задержку для exponential backoff.
        
        Formula: min(INITIAL_BACKOFF * (BACKOFF_FACTOR ^ retry_count), MAX_BACKOFF)
        
        Args:
            retry_count: Текущее количество повторов
            
        Returns:
            float: Задержка в секундах
        """
        delay = cls.INITIAL_BACKOFF * (cls.BACKOFF_FACTOR ** retry_count)
        return min(delay, cls.MAX_BACKOFF)


class AgentConfig:
    """
    Общие конфигурации для агентов.
    """
    
    # Максимальный размер payload (bytes)
    MAX_PAYLOAD_SIZE: int = 1024 * 1024  # 1MB
    
    # Максимальная длина message history (в памяти)
    MAX_MESSAGE_HISTORY: int = 1000
    
    # Включить ли подробное логирование
    VERBOSE_LOGGING: bool = True
    
    # Включить ли сбор метрик
    ENABLE_METRICS: bool = True
