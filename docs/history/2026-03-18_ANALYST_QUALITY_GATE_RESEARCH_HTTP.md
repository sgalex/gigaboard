# Актуализация: Analyst, Quality Gate, Research (18.03.2026)

## Executive Summary

Зафиксированы изменения в ядре мультиагентной системы, направленные на устойчивость к «битому» JSON от LLM у **AnalystAgent**, ограничение бессмысленных циклов **replan** при пустых `findings` у аналитика в **QualityGateAgent**, и повышение успешности загрузки URL в **ResearchAgent** за счёт браузероподобных HTTP-заголовков.

## Тезисы

- **AnalystAgent** (`agents/analyst.py`): при JSON-синтаксической ошибке в ответе модели — повторный вызов с требованием валидного JSON; при неудаче — best-effort извлечение insights/recommendations из сырого текста, чтобы не отдавать 0 findings только из-за формата ответа.
- **QualityGateAgent** (`agents/quality_gate.py`, ключ `validator`): эвристика «analyst без findings» может предложить `suggested_replan` только на первой итерации валидации; далее — `valid=false` без replan, чтобы Orchestrator не повторял один сценарий до лимита 3 раз.
- **ResearchAgent** (`agents/research.py`): заголовки запросов к URL приближены к обычному браузеру (Firefox-подобный `User-Agent` и сопутствующие поля).

## Документация

Подробное описание поведения и терминов — в **`docs/MULTI_AGENT.md`** (разделы Analyst, Research, Validator/Quality Gate). Краткая привязка к FR — в **`docs/SPECIFICATIONS.md`** (FR-7).

## Код (ориентиры)

- `apps/backend/app/services/multi_agent/agents/analyst.py`
- `apps/backend/app/services/multi_agent/agents/quality_gate.py`
- `apps/backend/app/services/multi_agent/agents/research.py`
