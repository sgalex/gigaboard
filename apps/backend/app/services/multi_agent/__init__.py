"""
Multi-Agent System V2 для GigaBoard.

V2: Единый Orchestrator, AgentPayload, zero-mapping.
См. docs/MULTI_AGENT_V2_CONCEPT.md для полной спецификации.

Модули:
- message_types: MessageType enum, AgentMessage schema
- message_bus: AgentMessageBus для pub/sub коммуникации
- orchestrator: Orchestrator V2 (единый путь)
- agents: Специализированные агенты (PlannerAgent, AnalystAgent, etc.)
- schemas: AgentPayload — универсальный формат данных
"""
from .message_types import MessageType, AgentMessage
from .message_bus import AgentMessageBus
from .exceptions import (
    MessageBusError,
    MessageDeliveryError,
    TimeoutError,
    AgentNotFoundError
)
from .orchestrator import Orchestrator
from .schemas.agent_payload import AgentPayload
from .agents import BaseAgent, PlannerAgent, AnalystAgent, ReporterAgent, QualityGateAgent

__all__ = [
    # V2 Orchestrator
    "Orchestrator",
    "AgentPayload",
    # Message Bus
    "MessageType",
    "AgentMessage",
    "AgentMessageBus",
    # Exceptions
    "MessageBusError",
    "MessageDeliveryError",
    "TimeoutError",
    "AgentNotFoundError",
    # V2 Agents
    "BaseAgent",
    "PlannerAgent",
    "AnalystAgent",
    "ReporterAgent",
    "QualityGateAgent",
]
