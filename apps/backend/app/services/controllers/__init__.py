"""
controllers/ — Satellite Controllers (V2).

Контроллеры инкапсулируют контекстную логику,
вызывая Orchestrator.process_request() и обрабатывая результат
для конкретного UI-компонента.

См. docs/MULTI_AGENT_V2_CONCEPT.md → Phase 4
"""

from .base_controller import BaseController, ControllerResult
from .transformation_controller import TransformationController
from .transform_suggestions_controller import TransformSuggestionsController
from .widget_controller import WidgetController
from .widget_suggestions_controller import WidgetSuggestionsController
from .ai_assistant_controller import AIAssistantController
from .document_extraction_controller import DocumentExtractionController
from .document_suggestions_controller import DocumentSuggestionsController
from .research_controller import ResearchController

__all__ = [
    "BaseController",
    "ControllerResult",
    "TransformationController",
    "TransformSuggestionsController",
    "WidgetController",
    "WidgetSuggestionsController",
    "AIAssistantController",
    "DocumentExtractionController",
    "DocumentSuggestionsController",
    "ResearchController",
]
