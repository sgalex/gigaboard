"""
Multi-Agent System для GigaBoard.

Phase 1: Message Bus Infrastructure (завершена 2026-01-29)
Phase 2: Orchestrator & Session Management (завершена 2026-01-29)
Phase 3: Agents Implementation (в разработке 2026-01-29)

Модули:
- message_types: MessageType enum, AgentMessage schema
- message_bus: AgentMessageBus для pub/sub коммуникации
- session: AgentSessionManager для управления сессиями
- orchestrator: MultiAgentOrchestrator для координации агентов
- agents: Специализированные агенты (PlannerAgent, AnalystAgent, etc.)
- timeout_monitor: Мониторинг таймаутов сообщений
- metrics: Сбор метрик и мониторинг

См. docs/MULTI_AGENT_SYSTEM.md для детальной документации.
"""
from .message_types import MessageType, AgentMessage
from .message_bus import AgentMessageBus
from .exceptions import (
    MessageBusError,
    MessageDeliveryError,
    TimeoutError,
    AgentNotFoundError
)
from .session import AgentSessionManager
from .orchestrator import MultiAgentOrchestrator
from .agents import BaseAgent, PlannerAgent, AnalystAgent, TransformationAgent, ReporterAgent, ResearcherAgent, SearchAgent

# Engine - главный фасад
from .engine import MultiAgentEngine

__all__ = [
    # Engine (главный фасад для AI Assistant)
    "MultiAgentEngine",
    # Message Bus
    "MessageType",
    "AgentMessage",
    "AgentMessageBus",
    # Exceptions
    "MessageBusError",
    "MessageDeliveryError",
    "TimeoutError",
    "AgentNotFoundError",
    # Session & Orchestration
    "AgentSessionManager",
    "MultiAgentOrchestrator",
    # Agents
    "BaseAgent",
    "PlannerAgent",
    "AnalystAgent",
    "TransformationAgent",
    "ReporterAgent",
    "ResearcherAgent",
    "SearchAgent",
]
