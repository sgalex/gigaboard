"""
Metrics и monitoring для Multi-Agent Message Bus.
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
from .message_types import MessageType

logger = logging.getLogger(__name__)


class MessageBusMetrics:
    """
    Сбор метрик для Message Bus.
    
    Отслеживает:
    - Количество сообщений по типам
    - Количество сообщений по агентам (отправителям/получателям)
    - Время доставки сообщений
    - Ошибки и таймауты
    """
    
    def __init__(self):
        # Счётчики по типам сообщений
        self.messages_by_type: Dict[MessageType, int] = defaultdict(int)
        
        # Счётчики по агентам
        self.messages_by_sender: Dict[str, int] = defaultdict(int)
        self.messages_by_receiver: Dict[str, int] = defaultdict(int)
        
        # Timing metrics (microseconds)
        self.delivery_times: List[float] = []
        
        # Error counts
        self.errors_by_type: Dict[str, int] = defaultdict(int)
        self.timeout_count: int = 0
        
        # Start time
        self.start_time = datetime.utcnow()
    
    def record_message_sent(
        self,
        message_type: MessageType,
        sender: str,
        receiver: str
    ):
        """Записать отправку сообщения."""
        self.messages_by_type[message_type] += 1
        self.messages_by_sender[sender] += 1
        self.messages_by_receiver[receiver] += 1
    
    def record_delivery_time(self, time_microseconds: float):
        """
        Записать время доставки сообщения.
        
        Args:
            time_microseconds: Время в микросекундах
        """
        self.delivery_times.append(time_microseconds)
        
        # Ограничиваем размер списка (храним последние 1000)
        if len(self.delivery_times) > 1000:
            self.delivery_times = self.delivery_times[-1000:]
    
    def record_error(self, error_type: str):
        """
        Записать ошибку.
        
        Args:
            error_type: Тип ошибки (timeout, delivery_failed, etc.)
        """
        self.errors_by_type[error_type] += 1
        
        if error_type == "timeout":
            self.timeout_count += 1
    
    def get_summary(self) -> Dict:
        """
        Получить сводку метрик.
        
        Returns:
            Dict с метриками
        """
        total_messages = sum(self.messages_by_type.values())
        uptime = (datetime.utcnow() - self.start_time).total_seconds()
        
        # Рассчитываем статистику по времени доставки
        avg_delivery_time = 0.0
        max_delivery_time = 0.0
        if self.delivery_times:
            avg_delivery_time = sum(self.delivery_times) / len(self.delivery_times)
            max_delivery_time = max(self.delivery_times)
        
        return {
            "uptime_seconds": uptime,
            "total_messages": total_messages,
            "messages_per_second": total_messages / uptime if uptime > 0 else 0,
            "messages_by_type": dict(self.messages_by_type),
            "top_senders": self._get_top_n(self.messages_by_sender, n=5),
            "top_receivers": self._get_top_n(self.messages_by_receiver, n=5),
            "delivery_time_avg_ms": avg_delivery_time / 1000,  # Convert to ms
            "delivery_time_max_ms": max_delivery_time / 1000,
            "total_errors": sum(self.errors_by_type.values()),
            "errors_by_type": dict(self.errors_by_type),
            "timeout_count": self.timeout_count,
        }
    
    def _get_top_n(self, counter: Dict, n: int = 5) -> List[tuple]:
        """Получить топ N элементов из counter."""
        return sorted(counter.items(), key=lambda x: x[1], reverse=True)[:n]


class MessageBusMonitor:
    """
    Мониторинг Message Bus с алертами при превышении порогов.
    
    Отслеживает:
    - Латентность (avg delivery time)
    - Throughput (messages/sec)
    - Error rate
    - Timeout rate
    
    Example:
        monitor = MessageBusMonitor(
            latency_threshold_ms=100,
            error_rate_threshold=0.05
        )
        
        # Периодически проверяем метрики
        alerts = monitor.check_thresholds(metrics)
        if alerts:
            for alert in alerts:
                logger.warning(f"ALERT: {alert}")
    """
    
    def __init__(
        self,
        latency_threshold_ms: float = 100.0,
        throughput_threshold: float = 100.0,
        error_rate_threshold: float = 0.05,
        timeout_rate_threshold: float = 0.02
    ):
        """
        Args:
            latency_threshold_ms: Максимальная латентность (ms)
            throughput_threshold: Минимальный throughput (msg/sec)
            error_rate_threshold: Максимальный error rate (0.05 = 5%)
            timeout_rate_threshold: Максимальный timeout rate (0.02 = 2%)
        """
        self.latency_threshold_ms = latency_threshold_ms
        self.throughput_threshold = throughput_threshold
        self.error_rate_threshold = error_rate_threshold
        self.timeout_rate_threshold = timeout_rate_threshold
        
        # История алертов
        self.alert_history: List[Dict] = []
    
    def check_thresholds(self, metrics: MessageBusMetrics) -> List[str]:
        """
        Проверить метрики на превышение порогов.
        
        Args:
            metrics: MessageBusMetrics для проверки
            
        Returns:
            List[str]: Список алертов (пустой если всё ок)
        """
        alerts = []
        summary = metrics.get_summary()
        
        # Проверка латентности
        if summary["delivery_time_avg_ms"] > self.latency_threshold_ms:
            alert = (
                f"High latency: {summary['delivery_time_avg_ms']:.2f}ms "
                f"(threshold: {self.latency_threshold_ms}ms)"
            )
            alerts.append(alert)
            self._record_alert("latency", alert)
        
        # Проверка throughput
        if summary["messages_per_second"] < self.throughput_threshold:
            alert = (
                f"Low throughput: {summary['messages_per_second']:.2f} msg/s "
                f"(threshold: {self.throughput_threshold} msg/s)"
            )
            alerts.append(alert)
            self._record_alert("throughput", alert)
        
        # Проверка error rate
        if summary["total_messages"] > 0:
            error_rate = summary["total_errors"] / summary["total_messages"]
            if error_rate > self.error_rate_threshold:
                alert = (
                    f"High error rate: {error_rate:.2%} "
                    f"(threshold: {self.error_rate_threshold:.2%})"
                )
                alerts.append(alert)
                self._record_alert("error_rate", alert)
            
            # Проверка timeout rate
            timeout_rate = summary["timeout_count"] / summary["total_messages"]
            if timeout_rate > self.timeout_rate_threshold:
                alert = (
                    f"High timeout rate: {timeout_rate:.2%} "
                    f"(threshold: {self.timeout_rate_threshold:.2%})"
                )
                alerts.append(alert)
                self._record_alert("timeout_rate", alert)
        
        return alerts
    
    def _record_alert(self, alert_type: str, message: str):
        """
        Записать алерт в историю.
        
        Args:
            alert_type: Тип алерта
            message: Сообщение алерта
        """
        self.alert_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "type": alert_type,
            "message": message,
        })
        
        # Ограничиваем историю (последние 100 алертов)
        if len(self.alert_history) > 100:
            self.alert_history = self.alert_history[-100:]
    
    def get_alert_history(
        self,
        since: Optional[datetime] = None,
        limit: int = 50
    ) -> List[Dict]:
        """
        Получить историю алертов.
        
        Args:
            since: Показать алерты начиная с этого времени
            limit: Максимальное количество алертов
            
        Returns:
            List[Dict]: Список алертов
        """
        if since is None:
            return self.alert_history[-limit:]
        
        filtered = [
            alert for alert in self.alert_history
            if datetime.fromisoformat(alert["timestamp"]) >= since
        ]
        
        return filtered[-limit:]
