"""
Timeout monitoring для отслеживания застрявших сообщений.
"""
import asyncio
import logging
from typing import Dict, Optional, Callable, Any
from datetime import datetime, timedelta
from .message_types import MessageType, AgentMessage
from .config import TimeoutConfig
from .exceptions import TimeoutError

logger = logging.getLogger(__name__)


class TimeoutMonitor:
    """
    Мониторинг таймаутов для сообщений в Message Bus.
    
    Отслеживает:
    - Сообщения, ожидающие ответа
    - Автоматическое создание ERROR messages при timeout
    - Алерты о застрявших сообщениях
    
    Example:
        monitor = TimeoutMonitor()
        await monitor.start()
        
        # Зарегистрировать сообщение для мониторинга
        await monitor.track_message(message, timeout=30)
        
        # Отметить, что ответ получен
        await monitor.mark_received(message.message_id)
    """
    
    def __init__(self, check_interval: float = 5.0):
        """
        Args:
            check_interval: Интервал проверки таймаутов (секунды)
        """
        self.check_interval = check_interval
        
        # Отслеживаемые сообщения: {message_id: (message, deadline, callback)}
        self.tracked_messages: Dict[str, tuple[AgentMessage, datetime, Optional[Callable]]] = {}
        
        # Флаг для остановки мониторинга
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None
        
        # Статистика
        self.stats = {
            "tracked_count": 0,
            "timeout_count": 0,
            "completed_count": 0,
        }
    
    async def start(self):
        """Запустить мониторинг таймаутов."""
        if self._running:
            logger.warning("TimeoutMonitor already running")
            return
        
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("TimeoutMonitor started")
    
    async def stop(self):
        """Остановить мониторинг."""
        self._running = False
        
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("TimeoutMonitor stopped")
    
    async def track_message(
        self,
        message: AgentMessage,
        timeout: Optional[int] = None,
        on_timeout: Optional[Callable[..., Any]] = None
    ):
        """
        Зарегистрировать сообщение для мониторинга таймаута.
        
        Args:
            message: Сообщение для отслеживания
            timeout: Таймаут в секундах (если None, берётся из TimeoutConfig)
            on_timeout: Callback функция при timeout (async)
        """
        if timeout is None:
            timeout = TimeoutConfig.get_timeout(
                message.message_type,
                message.sender
            )
        
        deadline = datetime.utcnow() + timedelta(seconds=timeout)
        
        self.tracked_messages[message.message_id] = (message, deadline, on_timeout)
        self.stats["tracked_count"] += 1
        
        logger.debug(
            f"Tracking message {message.message_id} with {timeout}s timeout"
        )
    
    async def mark_received(self, message_id: str):
        """
        Отметить, что ответ на сообщение получен.
        
        Args:
            message_id: ID сообщения (или parent_message_id ответа)
        """
        if message_id in self.tracked_messages:
            del self.tracked_messages[message_id]
            self.stats["completed_count"] += 1
            logger.debug(f"Message {message_id} completed before timeout")
    
    async def _monitor_loop(self):
        """Фоновая задача для проверки таймаутов."""
        logger.info("Timeout monitoring loop started")
        
        try:
            while self._running:
                await asyncio.sleep(self.check_interval)
                await self._check_timeouts()
                
        except asyncio.CancelledError:
            logger.info("Timeout monitoring loop cancelled")
        except Exception as e:
            logger.error(f"Error in timeout monitoring loop: {e}")
    
    async def _check_timeouts(self):
        """Проверить все отслеживаемые сообщения на таймаут."""
        now = datetime.utcnow()
        timed_out = []
        
        for message_id, (message, deadline, on_timeout) in self.tracked_messages.items():
            if now >= deadline:
                timed_out.append((message_id, message, on_timeout))
        
        # Обрабатываем таймауты
        for message_id, message, on_timeout in timed_out:
            await self._handle_timeout(message_id, message, on_timeout)
    
    async def _handle_timeout(
        self,
        message_id: str,
        message: AgentMessage,
        on_timeout: Optional[Callable[..., Any]]
    ):
        """
        Обработать таймаут сообщения.
        
        Args:
            message_id: ID сообщения
            message: Само сообщение
            on_timeout: Callback функция
        """
        # Удаляем из отслеживаемых
        del self.tracked_messages[message_id]
        self.stats["timeout_count"] += 1
        
        logger.warning(
            f"Message {message_id} timed out. "
            f"Type: {message.message_type}, "
            f"Sender: {message.sender}, "
            f"Receiver: {message.receiver}"
        )
        
        # Вызываем callback если есть
        if on_timeout:
            try:
                await on_timeout(message)
            except Exception as e:
                logger.error(f"Error in timeout callback: {e}")
    
    def get_stats(self) -> Dict:
        """Получить статистику мониторинга."""
        return {
            **self.stats,
            "currently_tracking": len(self.tracked_messages),
        }
    
    def get_tracked_messages(self) -> Dict[str, Dict]:
        """
        Получить список отслеживаемых сообщений с их оставшимся временем.
        
        Returns:
            Dict: {message_id: {"time_left_seconds": ..., "message_type": ...}}
        """
        now = datetime.utcnow()
        result = {}
        
        for message_id, (message, deadline, _) in self.tracked_messages.items():
            time_left = (deadline - now).total_seconds()
            result[message_id] = {
                "message_type": message.message_type,
                "sender": message.sender,
                "receiver": message.receiver,
                "time_left_seconds": max(0, time_left),
            }
        
        return result
