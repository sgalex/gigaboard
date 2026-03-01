"""
ResolverService — утилитарный сервис для AI-резолвинга данных (V2).

Бывший ResolverAgent, вынесен из agents/ в services/.
**Не агент** — не наследует BaseAgent, не использует MessageBus,
не вызывается Orchestrator'ом.

Это runtime-утилита, доступная в коде трансформаций через
``gb.ai_resolve_batch()`` и ``gb.ai_resolve_single()``.

Интерфейс без изменений по сравнению с V1.

См. docs/MULTI_AGENT_V2_CONCEPT.md → Phase 4.7
"""

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("resolver_service")


class ResolverService:
    """
    Утилитарный сервис для AI batch-резолвинга данных.

    Умеет:
    - Обрабатывать batch запросы (списки значений)
    - Автоматически разбивать на чанки
    - Формировать промпты и парсить JSON ответы
    - Возвращать результаты в фиксированном порядке

    Примеры использования (в сгенерированном коде):
    - Определить пол по имени
    - Определить страну по городу
    - Sentiment analysis
    - Категоризация товаров
    """

    DEFAULT_SYSTEM_PROMPT = (
        "You are a data resolver assistant. Your task is to resolve "
        "data values based on context.\n\n"
        "Rules:\n"
        "- Analyze the task and input values\n"
        "- Return structured JSON results\n"
        "- Be consistent across similar inputs\n"
        "- If uncertain, return null\n"
        "- Process all values in the batch"
    )

    def __init__(
        self,
        gigachat_service: Any,
        system_prompt: Optional[str] = None,
    ):
        """
        Args:
            gigachat_service: Инициализированный GigaChatService.
            system_prompt: Кастомный system prompt (optional).
        """
        self.gigachat = gigachat_service
        self.system_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT

    # ══════════════════════════════════════════════════════════════════
    #  Public API
    # ══════════════════════════════════════════════════════════════════

    async def resolve_batch(
        self,
        values: List[Any],
        task_description: str,
        result_format: str = "string",
        chunk_size: int = 50,
    ) -> Dict[str, Any]:
        """
        Резолвит batch значений через GigaChat.

        Args:
            values: Список значений для резолвинга.
            task_description: Описание задачи ("определи пол по имени").
            result_format: Формат одного результата ("string" | "number" | "json").
            chunk_size: Размер чанка для разбиения.

        Returns:
            {
                "results": [result1, result2, ...],
                "count": int,
                "task_description": str,
            }
        """
        try:
            logger.info(
                f"Resolving {len(values)} values: '{task_description[:50]}...'"
            )

            chunks = [
                values[i : i + chunk_size]
                for i in range(0, len(values), chunk_size)
            ]
            all_results: List[Any] = []

            for chunk_idx, chunk in enumerate(chunks):
                logger.info(
                    f"Processing chunk {chunk_idx + 1}/{len(chunks)} "
                    f"({len(chunk)} values)"
                )

                prompt = self._build_resolve_prompt(
                    values=chunk,
                    task_description=task_description,
                    result_format=result_format,
                )

                messages = [
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt},
                ]

                response = await self.gigachat.chat_completion(
                    messages=messages,
                    temperature=0.1,  # Низкая температура для consistency
                    max_tokens=2000,
                )

                chunk_results = self._parse_resolve_response(
                    response, expected_count=len(chunk)
                )
                all_results.extend(chunk_results)

            logger.info(f"Resolved {len(all_results)} values successfully")

            return {
                "results": all_results,
                "count": len(all_results),
                "task_description": task_description,
            }

        except Exception as e:
            logger.error(f"Batch resolve failed: {e}")
            return {
                "error": f"Resolve failed: {str(e)}",
                "results": [None] * len(values),
                "count": len(values),
            }

    async def resolve_single(
        self,
        value: Any,
        task_description: str,
    ) -> Any:
        """Резолвит одно значение (обёртка над resolve_batch)."""
        result = await self.resolve_batch([value], task_description)
        results = result.get("results", [None])
        return results[0] if results else None

    # ══════════════════════════════════════════════════════════════════
    #  Prompt building
    # ══════════════════════════════════════════════════════════════════

    @staticmethod
    def _build_resolve_prompt(
        values: List[Any],
        task_description: str,
        result_format: str,
    ) -> str:
        """Формирует промпт для резолвинга."""
        values_list = "\n".join(
            [f"{i + 1}. {v}" for i, v in enumerate(values)]
        )

        return (
            f"TASK: {task_description}\n\n"
            f"INPUT VALUES ({len(values)} total):\n"
            f"{values_list}\n\n"
            f"REQUIREMENTS:\n"
            f"- Process ALL {len(values)} input values listed above\n"
            f"- Return results in the SAME ORDER as input (1, 2, 3, ...)\n"
            f"- Use consistent logic across all values\n"
            f"- If value cannot be resolved, return null\n\n"
            f"Return ONLY valid JSON in this format:\n"
            f'{{\n  "results": [result1, result2, result3, ...]\n}}\n\n'
            f"CRITICAL:\n"
            f"- Array length MUST be exactly {len(values)}\n"
            f"- Results must match input order exactly\n"
            f"- Use simple {result_format} values\n"
            f"- No extra text, only JSON"
        )

    # ══════════════════════════════════════════════════════════════════
    #  Response parsing
    # ══════════════════════════════════════════════════════════════════

    @staticmethod
    def _parse_resolve_response(
        response: str,
        expected_count: int,
    ) -> List[Any]:
        """Парсит ответ от GigaChat."""
        try:
            clean = response.strip()

            # Убираем маркеры кода
            if clean.startswith("```json"):
                clean = clean[7:]
            elif clean.startswith("```"):
                clean = clean[3:]
            if clean.endswith("```"):
                clean = clean[:-3]
            clean = clean.strip()

            parsed = json.loads(clean)

            if "results" in parsed and isinstance(parsed["results"], list):
                results = parsed["results"]

                # Выравнивание количества
                if len(results) < expected_count:
                    logger.warning(
                        f"Result count mismatch: expected {expected_count}, "
                        f"got {len(results)} — padding with null"
                    )
                    results.extend([None] * (expected_count - len(results)))
                elif len(results) > expected_count:
                    results = results[:expected_count]

                return results

            logger.error(f"Invalid response format: {parsed}")
            return [None] * expected_count

        except Exception as e:
            logger.error(f"Failed to parse response: {e}")
            return [None] * expected_count


# ══════════════════════════════════════════════════════════════════════
#  Factory
# ══════════════════════════════════════════════════════════════════════


def get_resolver_service(
    gigachat_service: Optional[Any] = None,
) -> ResolverService:
    """
    Создаёт экземпляр ResolverService.

    Args:
        gigachat_service: GigaChatService instance (если None — получает singleton).
    """
    if not gigachat_service:
        from app.services.gigachat_service import get_gigachat_service

        gigachat_service = get_gigachat_service()

    return ResolverService(gigachat_service=gigachat_service)
