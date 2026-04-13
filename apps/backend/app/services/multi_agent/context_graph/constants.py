"""
Константы контекстного графа.

Ключ привязки LLM для механизмов, не являющихся шагами плана (сжатие L1/L2 и т.п.).
В админке — та же таблица agent_llm_override, что и для агентов.

Если отдельной привязки для этого ключа нет, LLMRouter использует тот же system default,
что и для planner/analyst и др. (см. LLMRouter._resolve_llm_config).
"""

# См. docs/LLM_CONFIGURATION_CONCEPT.md — зарезервированные ключи привязки
CONTEXT_GRAPH_COMPRESSION_AGENT_KEY = "context_graph_compression"
