"""
GigaBoard Multi-Agent System V2 - Agents

V2 Core Agents (используются через Orchestrator):
- BaseAgent - базовый класс для всех агентов
- PlannerAgent - планирование и декомпозиция задач
- DiscoveryAgent - обнаружение источников данных
- ResearchAgent - исследование и сбор данных
- StructurizerAgent - структуризация контента
- AnalystAgent - анализ данных
- TransformCodexAgent - генерация кода (трансформации)
- WidgetCodexAgent - генерация HTML/CSS/JS виджетов (визуализации)
- ReporterAgent - генерация отчётов и нарративов
- QualityGateAgent - pipeline-level валидация результатов

Утилитарные агенты:
- ValidatorAgent (validator.py) - code-level валидация (синтаксис, безопасность)
- ResolverAgent (resolver.py) - AI batch resolution
"""

from .base import BaseAgent
from .planner import PlannerAgent
from .analyst import AnalystAgent
from .reporter import ReporterAgent
from .quality_gate import QualityGateAgent
from .widget_codex import WidgetCodexAgent
from .transform_codex import TransformCodexAgent

__all__ = [
    "BaseAgent",
    "PlannerAgent",
    "AnalystAgent",
    "ReporterAgent",
    "QualityGateAgent",
    "WidgetCodexAgent",
    "TransformCodexAgent",
]
