"""
AI Data Generator Service - генерация синтетических данных через AI.

См. docs/AI_ASSISTANT.md
"""
import logging
import json
from typing import List, Dict, Any, Tuple
from .gigachat_service import get_gigachat_service

logger = logging.getLogger(__name__)


class AIDataGenerator:
    """
    Сервис для генерации структурированных данных через AI.
    
    Преобразует естественный запрос пользователя в JSON данные.
    """
    
    SYSTEM_PROMPT = """Ты — генератор синтетических данных для аналитической платформы GigaBoard.

Твоя задача:
1. Понять запрос пользователя о каких данных идёт речь
2. Сгенерировать реалистичные структурированные данные в формате JSON
3. Данные должны быть в виде массива объектов с одинаковой структурой

Требования к формату:
- Только валидный JSON (без markdown, без комментариев)
- Формат: [{"column1": value1, "column2": value2}, ...]
- Названия колонок на английском (snake_case)
- Значения должны быть разнообразными и реалистичными
- Минимум 20-30 записей, максимум 100
- Используй разные типы данных: числа, строки, даты, булевы значения

Примеры форматов дат:
- "2026-01-27" для дат
- "2026-01-27 15:30:00" для timestamp
- "2026-01-27T15:30:00Z" для ISO format

Примеры запросов и ответов:

Запрос: "Данные о продажах за месяц"
Ответ:
[
  {"date": "2026-01-01", "product": "Widget A", "quantity": 15, "revenue": 1499.50, "region": "North"},
  {"date": "2026-01-02", "product": "Widget B", "quantity": 8, "revenue": 799.20, "region": "South"},
  ...
]

Запрос: "Данные о пользователях"
Ответ:
[
  {"id": 1, "name": "John Doe", "email": "john@example.com", "age": 28, "is_active": true, "registered_at": "2025-06-15"},
  {"id": 2, "name": "Jane Smith", "email": "jane@example.com", "age": 35, "is_active": true, "registered_at": "2025-08-22"},
  ...
]

ВАЖНО: 
- Ответ должен содержать ТОЛЬКО JSON массив, без дополнительного текста
- Не используй markdown блоки кода (```json)
- Не добавляй пояснения или комментарии
"""
    
    def __init__(self):
        """Инициализация генератора."""
        self.gigachat = get_gigachat_service()
    
    async def generate_data_from_prompt(
        self,
        user_prompt: str,
        min_rows: int = 20,
        max_rows: int = 100
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Генерирует структурированные данные из текстового промпта.
        
        Args:
            user_prompt: Запрос пользователя (например, "Создай данные о продажах")
            min_rows: Минимальное количество строк
            max_rows: Максимальное количество строк
            
        Returns:
            (data, metadata) где:
                - data: список словарей с данными
                - metadata: {columns, row_count, column_types, source}
                
        Raises:
            Exception: при ошибках генерации или парсинга
        """
        try:
            # Формируем промпт с уточнениями
            enhanced_prompt = f"""Пользователь запросил: "{user_prompt}"

Сгенерируй от {min_rows} до {max_rows} записей данных в формате JSON массива.
Верни ТОЛЬКО JSON, без дополнительного текста."""
            
            # Запрос к GigaChat
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": enhanced_prompt}
            ]
            
            logger.info(f"Generating data for prompt: {user_prompt}")
            response = await self.gigachat.chat_completion(messages)
            
            # Очистка ответа от markdown и лишнего текста
            cleaned_response = self._clean_json_response(response)
            
            # Парсинг JSON
            try:
                data = json.loads(cleaned_response)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}\nResponse: {cleaned_response[:500]}")
                raise Exception(f"AI вернул некорректный JSON: {str(e)}")
            
            # Валидация структуры
            if not isinstance(data, list):
                raise Exception("AI должен вернуть массив объектов")
            
            if len(data) == 0:
                raise Exception("AI вернул пустой массив данных")
            
            if not all(isinstance(item, dict) for item in data):
                raise Exception("Все элементы массива должны быть объектами")
            
            # Ограничение по количеству
            if len(data) > max_rows:
                data = data[:max_rows]
                logger.warning(f"Truncated data to {max_rows} rows")
            
            # Извлечение метаданных
            columns = list(data[0].keys()) if data else []
            column_types = self._infer_column_types(data, columns)
            
            metadata = {
                "columns": columns,
                "column_types": column_types,
                "row_count": len(data),
                "total_row_count": len(data),
                "source": "ai_generated",
                "prompt": user_prompt,
                "from_cache": False,
            }
            
            logger.info(
                f"Generated {len(data)} rows with columns: {', '.join(columns)}"
            )
            
            return data, metadata
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            raise Exception(f"Не удалось распарсить ответ AI: {str(e)}")
        except Exception as e:
            logger.error(f"Error generating data: {e}")
            raise
    
    def _clean_json_response(self, response: str) -> str:
        """
        Очищает ответ от markdown и лишнего текста.
        
        Args:
            response: Сырой ответ от AI
            
        Returns:
            Очищенный JSON
        """
        # Удаляем markdown блоки кода
        if "```json" in response:
            # Извлекаем содержимое между ```json и ```
            start = response.find("```json") + 7
            end = response.find("```", start)
            if end != -1:
                response = response[start:end]
        elif "```" in response:
            # Просто ```
            start = response.find("```") + 3
            end = response.find("```", start)
            if end != -1:
                response = response[start:end]
        
        # Удаляем leading/trailing whitespace
        response = response.strip()
        
        # Если ответ содержит текст до JSON, пытаемся найти JSON
        if not response.startswith("[") and not response.startswith("{"):
            # Ищем начало JSON массива
            bracket_index = response.find("[")
            if bracket_index != -1:
                response = response[bracket_index:]
        
        return response
    
    def _infer_column_types(
        self,
        data: List[Dict[str, Any]],
        columns: List[str]
    ) -> Dict[str, str]:
        """
        Определить типы колонок по данным.
        
        Args:
            data: Список словарей с данными
            columns: Список названий колонок
            
        Returns:
            Словарь {column_name: type_name}
        """
        if not data or not columns:
            return {}
        
        types = {}
        
        for col in columns:
            # Берем первое непустое значение
            sample_value = None
            for row in data[:10]:  # Смотрим первые 10 строк
                if col in row and row[col] not in (None, "", "null"):
                    sample_value = row[col]
                    break
            
            if sample_value is None:
                types[col] = "string"
            elif isinstance(sample_value, bool):
                types[col] = "boolean"
            elif isinstance(sample_value, int):
                types[col] = "integer"
            elif isinstance(sample_value, float):
                types[col] = "float"
            elif isinstance(sample_value, (list, tuple)):
                types[col] = "array"
            elif isinstance(sample_value, dict):
                types[col] = "object"
            else:
                # Проверяем, может быть это дата
                if self._looks_like_date(str(sample_value)):
                    types[col] = "date"
                else:
                    types[col] = "string"
        
        return types
    
    def _looks_like_date(self, value: str) -> bool:
        """Проверяет, похоже ли значение на дату."""
        date_patterns = [
            "-",  # 2026-01-27
            "/",  # 01/27/2026
            "T",  # ISO format
        ]
        return any(pattern in value for pattern in date_patterns) and len(value) >= 8


def get_ai_data_generator() -> AIDataGenerator:
    """Get singleton instance of AI data generator."""
    return AIDataGenerator()
