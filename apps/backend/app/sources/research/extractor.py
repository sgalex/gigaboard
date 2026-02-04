"""Research Source Extractor - AI deep research via multi-agent.

Использует цепочку агентов SearchAgent → ResearcherAgent → AnalystAgent
для поиска и структурирования данных из открытых источников.
"""
import time
from typing import Any

from app.sources.base import (
    BaseSource,
    ExtractionResult,
    ValidationResult,
    TableData,
)


class ResearchSource(BaseSource):
    """AI Research source handler using multi-agent system."""
    
    source_type = "research"
    display_name = "AI Research"
    icon = "🔍"
    description = "Поиск данных через AI-агентов"
    
    async def validate_config(self, config: dict[str, Any]) -> ValidationResult:
        """Validate research source config."""
        errors = []
        
        if not config.get("initial_prompt"):
            errors.append("Необходимо указать запрос для исследования")
        
        if errors:
            return ValidationResult.failure(errors)
        return ValidationResult.success()
    
    async def extract(
        self,
        config: dict[str, Any],
        file_content: bytes | None = None,
        **kwargs
    ) -> ExtractionResult:
        """Execute deep research using multi-agent system."""
        start_time = time.time()
        
        try:
            initial_prompt = config.get("initial_prompt", "")
            
            # Get multi-agent engine from kwargs
            multi_agent_engine = kwargs.get("multi_agent_engine")
            
            if multi_agent_engine:
                # Execute research through multi-agent system
                result = await self._run_research(multi_agent_engine, initial_prompt, config)
                return result
            else:
                # Fallback: return placeholder
                return ExtractionResult(
                    success=True,
                    text=f"Исследование по запросу: '{initial_prompt}'\n\n"
                         "Мультиагентная система не доступна. "
                         "Для полноценного исследования необходимо настроить GigaChat API.",
                    tables=[],
                    extraction_time_ms=int((time.time() - start_time) * 1000),
                    metadata={
                        "prompt": initial_prompt,
                        "multi_agent_available": False,
                    }
                )
            
        except Exception as e:
            return ExtractionResult.failure(f"Ошибка исследования: {str(e)}")
    
    async def _run_research(
        self,
        engine: Any,
        prompt: str,
        config: dict[str, Any]
    ) -> ExtractionResult:
        """Run research through multi-agent engine.
        
        Цепочка: SearchAgent → ResearcherAgent → AnalystAgent
        """
        start_time = time.time()
        
        try:
            # Create research task
            task = {
                "type": "research",
                "prompt": prompt,
                "context": config.get("context", {}),
            }
            
            # Execute through engine
            # result = await engine.process_task(task)
            
            # TODO: Integrate with actual MultiAgentEngine
            # For now, return placeholder
            
            return ExtractionResult(
                success=True,
                text=f"Исследование по запросу: '{prompt}'\n\n"
                     "Результаты исследования будут здесь после интеграции с мультиагентом.",
                tables=[],
                extraction_time_ms=int((time.time() - start_time) * 1000),
                metadata={
                    "prompt": prompt,
                    "sources": [],
                }
            )
            
        except Exception as e:
            return ExtractionResult.failure(f"Ошибка мультиагента: {str(e)}")
    
    def get_dialog_schema(self) -> dict[str, Any]:
        """Get JSON Schema for research dialog."""
        return {
            "type": "object",
            "properties": {
                "initial_prompt": {
                    "type": "string",
                    "format": "textarea",
                    "title": "Запрос для исследования",
                    "description": "Опишите, какие данные нужно найти",
                },
            },
            "required": ["initial_prompt"],
        }
