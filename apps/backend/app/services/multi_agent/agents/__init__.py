"""
GigaBoard Multi-Agent System - Agents
Phase 3: Agents Implementation

Exported agents:
- BaseAgent - базовый класс для всех агентов
- PlannerAgent - оркестратор и декомпозиция задач
- AnalystAgent - анализ данных и SQL генерация
- TransformationAgent - генерация Python кода для трансформаций
- ReporterAgent - генерация WidgetNode визуализаций
- ResearcherAgent - получение данных из внешних источников
- SearchAgent - поиск информации в интернете через DuckDuckGo
- CriticAgent - валидация результатов Multi-Agent системы
- DeveloperAgent - кастомные инструменты (TODO)
- ExecutorAgent - выполнение кода в песочнице (TODO)
- FormGeneratorAgent - динамические формы (TODO)
- DataDiscoveryAgent - поиск публичных датасетов (TODO)
"""

from .base import BaseAgent
from .planner import PlannerAgent
from .analyst import AnalystAgent
from .transformation import TransformationAgent
from .reporter import ReporterAgent
from .researcher import ResearcherAgent
from .search import SearchAgent
from .error_analyzer import ErrorAnalyzerAgent, get_error_analyzer_agent
from .critic import CriticAgent, determine_expected_outcome, ExpectedOutcome

__all__ = [
    "BaseAgent",
    "PlannerAgent",
    "AnalystAgent",
    "TransformationAgent",
    "ReporterAgent",
    "ResearcherAgent",
    "SearchAgent",
    "ErrorAnalyzerAgent",
    "get_error_analyzer_agent",
    "CriticAgent",
    "determine_expected_outcome",
    "ExpectedOutcome",
]
