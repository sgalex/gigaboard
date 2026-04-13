"""
Инициализация и доступ к context_graph в pipeline_context.
"""

from __future__ import annotations

from typing import Any, Dict


def init_context_graph(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Создаёт пустой граф версии 1. Идемпотентно: если уже есть валидная структура — не затирает.
    """
    existing = pipeline_context.get("context_graph")
    if isinstance(existing, dict) and existing.get("version") == 1 and "nodes" in existing:
        return existing

    graph: Dict[str, Any] = {
        "version": 1,
        "nodes": {},
        "edges": [],
        "ingest_seq": 0,
    }
    pipeline_context["context_graph"] = graph
    return graph


def ensure_context_graph(pipeline_context: Dict[str, Any]) -> Dict[str, Any]:
    """Возвращает граф, создавая при необходимости."""
    g = pipeline_context.get("context_graph")
    if isinstance(g, dict) and g.get("version") == 1 and "nodes" in g:
        return g
    return init_context_graph(pipeline_context)
