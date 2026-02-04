"""
Тесты для CriticAgent — валидации результатов Multi-Agent системы.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from apps.backend.app.services.multi_agent.agents.critic import (
    CriticAgent,
    ExpectedOutcome,
    determine_expected_outcome,
    CRITIC_SYSTEM_PROMPT
)


class TestDetermineExpectedOutcome:
    """Тесты для функции determine_expected_outcome."""
    
    def test_code_generation_detected(self):
        """Проверяем определение code_generation по ключевым словам."""
        assert determine_expected_outcome("напиши код для парсинга") == "code_generation"
        assert determine_expected_outcome("сгенерируй python скрипт") == "code_generation"
        assert determine_expected_outcome("создай программу") == "code_generation"
        assert determine_expected_outcome("напиши SQL запрос") == "code_generation"
    
    def test_visualization_detected(self):
        """Проверяем определение visualization."""
        assert determine_expected_outcome("построй график продаж") == "visualization"
        assert determine_expected_outcome("визуализируй данные") == "visualization"
        assert determine_expected_outcome("покажи на диаграмме") == "visualization"
    
    def test_transformation_detected(self):
        """Проверяем определение transformation."""
        assert determine_expected_outcome("трансформируй данные") == "transformation"
        assert determine_expected_outcome("преобразуй таблицу") == "transformation"
        assert determine_expected_outcome("добавь столбец с возрастом") == "transformation"
        assert determine_expected_outcome("отфильтруй данные по дате") == "transformation"
    
    def test_data_extraction_detected(self):
        """Проверяем определение data_extraction."""
        assert determine_expected_outcome("загрузи данные из API") == "data_extraction"
        assert determine_expected_outcome("получи данные о погоде") == "data_extraction"
        assert determine_expected_outcome("скачай CSV файл") == "data_extraction"
    
    def test_research_default(self):
        """Проверяем, что research — дефолтный тип."""
        assert determine_expected_outcome("расскажи о компании Apple") == "research"
        assert determine_expected_outcome("что такое блокчейн?") == "research"
        assert determine_expected_outcome("найди информацию о Bitcoin") == "research"


class TestCriticAgentHeuristics:
    """Тесты для эвристической валидации CriticAgent."""
    
    @pytest.fixture
    def critic_agent(self):
        """Создаёт CriticAgent с mock GigaChat."""
        mock_gigachat = MagicMock()
        return CriticAgent(
            message_bus=None,
            gigachat_service=mock_gigachat
        )
    
    def test_code_generation_with_code_block_valid(self, critic_agent):
        """Если ожидается код и есть code block — valid."""
        result = critic_agent._heuristic_validation(
            expected_outcome="code_generation",
            aggregated_result={
                "developer": {
                    "message": "Вот код:\n```python\nimport pandas as pd\ndf = pd.read_csv('data.csv')\n```"
                }
            },
            original_request="напиши код"
        )
        
        assert result["valid"] is True
        assert result["confidence"] >= 0.9
    
    def test_code_generation_without_code_invalid(self, critic_agent):
        """Если ожидается код, но его нет — invalid."""
        result = critic_agent._heuristic_validation(
            expected_outcome="code_generation",
            aggregated_result={
                "researcher": {
                    "message": "Я нашёл информацию о парсинге CSV файлов..."
                }
            },
            original_request="напиши код"
        )
        
        assert result["valid"] is False
        assert "issues" in result
        assert result["issues"][0]["type"] == "missing_code"
    
    def test_visualization_with_widget_valid(self, critic_agent):
        """Если ожидается визуализация и есть widget_type — valid."""
        result = critic_agent._heuristic_validation(
            expected_outcome="visualization",
            aggregated_result={
                "reporter": {
                    "widget_type": "line_chart",
                    "data_config": {"x": "date", "y": "value"}
                }
            },
            original_request="построй график"
        )
        
        assert result["valid"] is True
        assert result["confidence"] >= 0.85
    
    def test_visualization_without_widget_invalid(self, critic_agent):
        """Если ожидается визуализация, но её нет — invalid."""
        result = critic_agent._heuristic_validation(
            expected_outcome="visualization",
            aggregated_result={
                "analyst": {
                    "insights": ["Тренд положительный", "Рост 10%"]
                }
            },
            original_request="построй график"
        )
        
        assert result["valid"] is False
        assert "issues" in result
    
    def test_transformation_with_df_result_valid(self, critic_agent):
        """Если ожидается трансформация и есть df_result + pandas — valid."""
        result = critic_agent._heuristic_validation(
            expected_outcome="transformation",
            aggregated_result={
                "transformation": {
                    "code": "df_result = df.groupby('category').sum()",
                    "message": "Трансформация выполнена"
                }
            },
            original_request="сгруппируй данные"
        )
        
        assert result["valid"] is True
    
    def test_research_with_text_valid(self, critic_agent):
        """Для research любой текстовый ответ приемлем."""
        result = critic_agent._heuristic_validation(
            expected_outcome="research",
            aggregated_result={
                "researcher": {
                    "message": "Bitcoin — это криптовалюта, созданная в 2009 году Сатоши Накамото..."
                }
            },
            original_request="расскажи о Bitcoin"
        )
        
        assert result["valid"] is True


class TestCriticAgentValidateMethod:
    """Тесты для публичного метода validate."""
    
    @pytest.fixture
    def critic_agent(self):
        """Создаёт CriticAgent с mock GigaChat."""
        mock_gigachat = AsyncMock()
        mock_gigachat.chat_completion = AsyncMock(return_value='{"valid": true, "confidence": 0.95}')
        return CriticAgent(
            message_bus=None,
            gigachat_service=mock_gigachat
        )
    
    @pytest.mark.asyncio
    async def test_validate_auto_detects_outcome(self, critic_agent):
        """Проверяем, что validate автоматически определяет expected_outcome."""
        result = await critic_agent.validate(
            user_message="напиши код для парсинга",
            aggregated_result={
                "developer": {
                    "code": "```python\nimport json\n```"
                }
            },
            expected_outcome=None,  # Должен определиться автоматически
            iteration=1
        )
        
        # Должен пройти heuristic validation (код присутствует)
        assert result["valid"] is True
    
    @pytest.mark.asyncio
    async def test_validate_uses_provided_outcome(self, critic_agent):
        """Проверяем, что validate использует переданный expected_outcome."""
        result = await critic_agent.validate(
            user_message="любой запрос",
            aggregated_result={
                "researcher": {"message": "Информация найдена"}
            },
            expected_outcome="research",
            iteration=1
        )
        
        assert result["valid"] is True


class TestCriticAgentExpectedOutcome:
    """Тесты для enum ExpectedOutcome."""
    
    def test_all_outcomes_have_values(self):
        """Проверяем, что все outcomes определены."""
        assert ExpectedOutcome.CODE_GENERATION.value == "code_generation"
        assert ExpectedOutcome.DATA_EXTRACTION.value == "data_extraction"
        assert ExpectedOutcome.VISUALIZATION.value == "visualization"
        assert ExpectedOutcome.TRANSFORMATION.value == "transformation"
        assert ExpectedOutcome.RESEARCH.value == "research"


class TestCriticAgentSystemPrompt:
    """Тесты для system prompt."""
    
    def test_system_prompt_contains_key_sections(self):
        """Проверяем, что system prompt содержит ключевые секции."""
        assert "CriticAgent" in CRITIC_SYSTEM_PROMPT
        assert "code_generation" in CRITIC_SYSTEM_PROMPT
        assert "visualization" in CRITIC_SYSTEM_PROMPT
        assert "transformation" in CRITIC_SYSTEM_PROMPT
        assert "research" in CRITIC_SYSTEM_PROMPT
        assert "valid" in CRITIC_SYSTEM_PROMPT
        assert "confidence" in CRITIC_SYSTEM_PROMPT


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
