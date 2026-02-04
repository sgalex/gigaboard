"""
ResolverAgent - AI-резолвинг данных через GigaChat.

Примеры задач:
- Определить пол по имени
- Определить страну по городу
- Извлечь тональность из текста
- Классифицировать товары по категориям
"""
import logging
from typing import Dict, Any, Optional, List
import json

from .base import BaseAgent
from ..message_bus import AgentMessageBus
from app.services.gigachat_service import GigaChatService


class ResolverAgent(BaseAgent):
    """
    Агент для AI-резолвинга данных.
    
    Умеет:
    - Обрабатывать batch запросы (списки значений)
    - Автоматически формировать промпты
    - Возвращать структурированные результаты
    """
    
    def __init__(
        self,
        message_bus: Optional[AgentMessageBus],
        gigachat_service: GigaChatService,
        system_prompt: Optional[str] = None
    ):
        # BaseAgent expects non-None message_bus, so we handle optional case
        if message_bus:
            super().__init__(
                agent_name="resolver",
                message_bus=message_bus,
                system_prompt=system_prompt
            )
        else:
            # Initialize without calling super().__init__
            self.agent_name = "resolver"
            self.system_prompt = system_prompt or self._get_default_system_prompt()
        
        self.gigachat = gigachat_service
        self.logger = logging.getLogger(f"agent.{self.agent_name}")
    
    def _get_default_system_prompt(self) -> str:
        return """You are a data resolver assistant. Your task is to resolve data values based on context.

Rules:
- Analyze the task and input values
- Return structured JSON results
- Be consistent across similar inputs
- If uncertain, return null
- Process all values in the batch"""
    
    def _validate_task(self, task: Dict[str, Any], required_fields: List[str]) -> None:
        """Validate task has required fields."""
        for field in required_fields:
            if field not in task:
                raise ValueError(f"Missing required field: {field}")
    
    def _format_error_response(self, error: str, suggestions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Format error response."""
        return {
            "error": error,
            "suggestions": suggestions or []
        }
    
    async def process_task(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Обрабатывает задачу резолвинга.
        
        Task format:
        {
            "type": "resolve_batch",
            "values": ["Alice", "Bob", "Charlie"],
            "task_description": "определи пол человека по имени",
            "result_format": "string"  # or "json", "number"
        }
        """
        task_type = task.get("type")
        
        if task_type == "resolve_batch":
            return await self._resolve_batch(task, context)
        else:
            return self._format_error_response(
                f"Unknown task type: {task_type}",
                suggestions=["Supported type: resolve_batch"]
            )
    
    async def _resolve_batch(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Резолвит batch значений через GigaChat."""
        try:
            self._validate_task(task, ["values", "task_description"])
            
            values = task["values"]
            task_description = task["task_description"]
            result_format = task.get("result_format", "string")
            chunk_size = task.get("chunk_size", 50)  # По умолчанию 50 значений в чанке
            
            self.logger.info(
                f"🔍 Resolving {len(values)} values: '{task_description}'"
            )
            
            # Разбиваем на чанки для больших батчей
            chunks = [values[i:i + chunk_size] for i in range(0, len(values), chunk_size)]
            all_results = []
            
            for chunk_idx, chunk in enumerate(chunks):
                self.logger.info(f"📦 Processing chunk {chunk_idx + 1}/{len(chunks)} ({len(chunk)} values)")
                
                # Формируем промпт для чанка
                resolve_prompt = self._build_resolve_prompt(
                    values=chunk,
                    task_description=task_description,
                    result_format=result_format
                )
                
                # Вызываем GigaChat
                messages = [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": resolve_prompt}
                ]
                
                response = await self.gigachat.chat_completion(
                    messages=messages,
                    temperature=0.1,  # Низкая температура для consistency
                    max_tokens=2000
                )
                
                # Парсим результаты
                chunk_results = self._parse_resolve_response(response, len(chunk))
                all_results.extend(chunk_results)
            
            self.logger.info(f"✅ Resolved {len(all_results)} values successfully")
            
            return {
                "results": all_results,
                "count": len(all_results),
                "task_description": task_description
            }
            
        except Exception as e:
            self.logger.error(f"❌ Batch resolve failed: {e}")
            return self._format_error_response(
                f"Resolve failed: {str(e)}",
                suggestions=["Check input format", "Try smaller batch size"]
            )
    
    def _build_resolve_prompt(
        self,
        values: List[Any],
        task_description: str,
        result_format: str
    ) -> str:
        """Формирует промпт для резолвинга."""
        
        # Форматируем все значения списком
        values_list = "\n".join([f"{i+1}. {v}" for i, v in enumerate(values)])
        
        prompt = f"""TASK: {task_description}

INPUT VALUES ({len(values)} total):
{values_list}

REQUIREMENTS:
- Process ALL {len(values)} input values listed above
- Return results in the SAME ORDER as input (1, 2, 3, ...)
- Use consistent logic across all values
- If value cannot be resolved, return null

Return ONLY valid JSON in this format:
{{
  "results": [result1, result2, result3, ...]
}}

CRITICAL: 
- Array length MUST be exactly {len(values)}
- Results must match input order exactly
- Use simple {result_format} values
- No extra text, only JSON
"""
        
        return prompt
    
    def _parse_resolve_response(self, response: str, expected_count: int) -> List[Any]:
        """Парсит ответ от GigaChat."""
        try:
            # Убираем маркеры кода если есть
            clean_response = response.strip()
            if clean_response.startswith("```json"):
                clean_response = clean_response[7:]
            elif clean_response.startswith("```"):
                clean_response = clean_response[3:]
            if clean_response.endswith("```"):
                clean_response = clean_response[:-3]
            clean_response = clean_response.strip()
            
            # Пытаемся распарсить JSON
            parsed = json.loads(clean_response)
            
            if "results" in parsed and isinstance(parsed["results"], list):
                results = parsed["results"]
                
                # Проверяем количество результатов
                if len(results) != expected_count:
                    self.logger.warning(
                        f"⚠️ Result count mismatch: expected {expected_count}, got {len(results)}"
                    )
                    # Дополняем или обрезаем до нужного размера
                    if len(results) < expected_count:
                        results.extend([None] * (expected_count - len(results)))
                    else:
                        results = results[:expected_count]
                
                return results
            
            # Если формат не тот, возвращаем null для всех значений
            self.logger.error(f"❌ Invalid response format: {parsed}")
            return [None] * expected_count
            
        except Exception as e:
            self.logger.error(f"❌ Failed to parse response: {e}")
            return [None] * expected_count


def get_resolver_agent(
    message_bus: Optional[AgentMessageBus] = None,
    gigachat_service: Optional[GigaChatService] = None
) -> ResolverAgent:
    """Создает экземпляр ResolverAgent."""
    if not gigachat_service:
        from ...gigachat_service import get_gigachat_service
        gigachat_service = get_gigachat_service()
    
    return ResolverAgent(message_bus, gigachat_service)
