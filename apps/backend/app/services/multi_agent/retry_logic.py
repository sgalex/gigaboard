"""
Retry logic с exponential backoff для Message Bus.
"""
import asyncio
import logging
from typing import Any, Callable, Optional
from .message_types import AgentMessage
from .message_bus import AgentMessageBus
from .config import RetryConfig
from .exceptions import RetryExhaustedError

logger = logging.getLogger(__name__)


async def send_with_retry(
    message_bus: AgentMessageBus,
    message: AgentMessage,
    max_retries: Optional[int] = None,
    backoff_factor: Optional[float] = None
) -> bool:
    """
    Отправить сообщение с retry logic при ошибках.
    
    Использует exponential backoff:
    - 1st retry: 1s delay
    - 2nd retry: 2s delay
    - 3rd retry: 4s delay
    
    Args:
        message_bus: Экземпляр MessageBus
        message: Сообщение для отправки
        max_retries: Максимальное количество попыток (по умолчанию из config)
        backoff_factor: Множитель для exponential backoff (по умолчанию из config)
    
    Returns:
        bool: True если успешно отправлено
        
    Raises:
        RetryExhaustedError: Если все попытки неудачны
    """
    max_retries = max_retries or RetryConfig.MAX_RETRIES
    backoff_factor = backoff_factor or RetryConfig.BACKOFF_FACTOR
    
    for attempt in range(max_retries):
        try:
            await message_bus.publish(message)
            
            if attempt > 0:
                logger.info(
                    f"Message {message.message_id} sent successfully on retry {attempt}"
                )
            
            return True
            
        except Exception as e:
            message.retry_count = attempt + 1
            
            # Если это последняя попытка, выбрасываем ошибку
            if attempt >= max_retries - 1:
                logger.error(
                    f"Failed to send message {message.message_id} after {max_retries} attempts: {e}"
                )
                raise RetryExhaustedError(
                    f"Message delivery failed after {max_retries} attempts: {e}"
                )
            
            # Exponential backoff
            delay = RetryConfig.get_backoff_delay(attempt)
            logger.warning(
                f"Failed to send message {message.message_id} (attempt {attempt + 1}/{max_retries}). "
                f"Retrying in {delay}s... Error: {e}"
            )
            
            await asyncio.sleep(delay)
    
    return False


async def retry_async_operation(
    operation: Callable,
    *args,
    max_retries: Optional[int] = None,
    backoff_factor: Optional[float] = None,
    operation_name: str = "operation",
    **kwargs
) -> Any:
    """
    Выполнить async операцию с retry logic.
    
    Универсальная функция для retry любых async операций.
    
    Args:
        operation: Async функция для выполнения
        *args: Позиционные аргументы для operation
        max_retries: Максимальное количество попыток
        backoff_factor: Множитель для exponential backoff
        operation_name: Название операции для логирования
        **kwargs: Именованные аргументы для operation
        
    Returns:
        Any: Результат выполнения operation
        
    Raises:
        RetryExhaustedError: Если все попытки неудачны
        
    Example:
        result = await retry_async_operation(
            some_async_func,
            arg1, arg2,
            max_retries=3,
            operation_name="fetch_data"
        )
    """
    max_retries = max_retries or RetryConfig.MAX_RETRIES
    backoff_factor = backoff_factor or RetryConfig.BACKOFF_FACTOR
    
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            result = await operation(*args, **kwargs)
            
            if attempt > 0:
                logger.info(
                    f"{operation_name} succeeded on retry {attempt}"
                )
            
            return result
            
        except Exception as e:
            last_exception = e
            
            # Если это последняя попытка, выбрасываем ошибку
            if attempt >= max_retries - 1:
                logger.error(
                    f"{operation_name} failed after {max_retries} attempts: {e}"
                )
                raise RetryExhaustedError(
                    f"{operation_name} failed after {max_retries} attempts: {e}"
                ) from last_exception
            
            # Exponential backoff
            delay = RetryConfig.get_backoff_delay(attempt)
            logger.warning(
                f"{operation_name} failed (attempt {attempt + 1}/{max_retries}). "
                f"Retrying in {delay}s... Error: {e}"
            )
            
            await asyncio.sleep(delay)
    
    # Should never reach here
    raise RetryExhaustedError(f"{operation_name} failed") from last_exception
