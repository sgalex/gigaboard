"""
LLM-сжатие резюме узла L0: L1 (короче) и L2 (одно предложение).

Результат хранится на том же узле: l1_summary, l2_one_liner.
Модель: привязка context_graph_compression или системный default (LLMRouter).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, Optional
from uuid import UUID

from ..runtime_overrides import ma_bool, ma_int
from .constants import CONTEXT_GRAPH_COMPRESSION_AGENT_KEY
from .store import ensure_context_graph

if TYPE_CHECKING:
    from app.services.llm_router import LLMRouter

logger = logging.getLogger(__name__)


def resolve_slice_node_body(
    node: Dict[str, Any],
    *,
    compaction_level: str,
) -> str:
    """
    Текст узла для push-среза context_graph в промпт.

    Семантика (pull-first / push-compact):
    - **full** (первый шаг context_ladder): **L1** при наличии, иначе L0; однострочный **L2** в квадратных
      скобках как якорь. Полный L0 в срез не кладём, если уже есть L1 — детализация через expand*-тулы.
    - **compact** (retry): сначала **L2**, иначе L1, иначе L0.
    - **minimal**: L2; иначе усечённый L1/L0 (лимиты env).
    """
    lvl = (compaction_level or "full").lower()
    l2 = str(node.get("l2_one_liner") or "").strip()
    l1 = str(node.get("l1_summary") or "").strip()
    l0 = str(node.get("summary_text") or "").strip()

    if lvl == "minimal":
        if l2:
            return l2
        cap1 = ma_int("MULTI_AGENT_CONTEXT_GRAPH_SLICE_MINIMAL_L1_MAX", 800)
        cap0 = ma_int("MULTI_AGENT_CONTEXT_GRAPH_SLICE_MINIMAL_L0_MAX", 1200)
        if l1:
            return (l1[:cap1] + "…") if len(l1) > cap1 else l1
        if l0:
            return (l0[:cap0] + "…") if len(l0) > cap0 else l0
        return ""

    if lvl == "compact":
        if l2:
            return l2
        if l1:
            return l1
        return l0

    # full — компактный push по умолчанию
    body = l1 if l1 else l0
    if l2 and body:
        return f"[{l2}]\n\n{body}"
    return body


async def maybe_compress_l0_node_with_llm(
    llm_router: "LLMRouter",
    *,
    user_id: Optional[UUID],
    pipeline_context: Dict[str, Any],
    l0_node_id: str,
) -> None:
    """
    Два вызова LLM: L1 сжатие summary_text, L2 одно предложение.
    При ошибке или выключенном флаге — no-op.
    """
    if not ma_bool("MULTI_AGENT_CONTEXT_GRAPH_LLM_COMPRESSION", True):
        return

    graph = ensure_context_graph(pipeline_context)
    nodes = graph.get("nodes") or {}
    if not isinstance(nodes, dict):
        return
    node = nodes.get(l0_node_id)
    if not isinstance(node, dict) or int(node.get("level") or 0) != 0:
        return

    text = str(node.get("summary_text") or "").strip()
    min_chars = ma_int("MULTI_AGENT_CONTEXT_GRAPH_COMPRESSION_MIN_L0_CHARS", 120)
    if len(text) < min_chars:
        return

    from app.services.llm_router import LLMCallParams, LLMMessage

    target_l1 = max(180, min(len(text) // 2, 6000))
    sys_l1 = (
        "Ты сжимаешь служебные резюме шагов пайплайна аналитики. "
        "Сохрани факты, имена, числа, статусы. Ответ — только сжатый текст, без вступлений."
    )
    user_l1 = (
        f"Сожми текст до примерно {target_l1} символов (можно чуть меньше).\n\n---\n"
        f"{text[:14000]}\n---"
    )

    try:
        raw_l1 = await llm_router.chat_completion(
            user_id=user_id,
            params=LLMCallParams(
                messages=[
                    LLMMessage(role="system", content=sys_l1),
                    LLMMessage(role="user", content=user_l1),
                ],
                temperature=0.2,
                max_tokens=min(2048, target_l1 // 3 + 500),
            ),
            agent_key=CONTEXT_GRAPH_COMPRESSION_AGENT_KEY,
        )
    except Exception as e:
        logger.warning("context_graph L1 compression failed for node %s: %s", l0_node_id, e)
        return

    l1 = (raw_l1 or "").strip()
    if not l1:
        return
    if len(l1) > len(text) * 1.15:
        l1 = text[:target_l1] + ("…" if len(text) > target_l1 else "")
    max_l1_store = ma_int("MULTI_AGENT_CONTEXT_GRAPH_L1_MAX_STORE_CHARS", 8000)
    node["l1_summary"] = l1[:max_l1_store]

    sys_l2 = (
        "Перепиши вход в ровно одно короткое предложение на русском. Только предложение, без кавычек и преамбулы."
    )
    user_l2 = f"Текст:\n\n{l1[:4500]}"
    try:
        raw_l2 = await llm_router.chat_completion(
            user_id=user_id,
            params=LLMCallParams(
                messages=[
                    LLMMessage(role="system", content=sys_l2),
                    LLMMessage(role="user", content=user_l2),
                ],
                temperature=0.15,
                max_tokens=180,
            ),
            agent_key=CONTEXT_GRAPH_COMPRESSION_AGENT_KEY,
        )
    except Exception as e:
        logger.warning("context_graph L2 compression failed for node %s: %s", l0_node_id, e)
        node["compression_partial"] = True
        node["compression_at"] = datetime.now(timezone.utc).isoformat()
        _emit = pipeline_context.get("_trace_event")
        if callable(_emit):
            _emit(
                event="context_graph_llm_compressed",
                phase="context_graph",
                details={
                    "l0_node_id": l0_node_id,
                    "l0_chars": len(text),
                    "l1_chars": len(str(node.get("l1_summary") or "")),
                    "l2_chars": 0,
                    "partial": True,
                },
            )
        if ma_bool("MULTI_AGENT_CONTEXT_EXPAND_COMPACT_LOG", False):
            logger.info(
                "[context_graph_compress] node=%s partial_after_l1 l0=%s l1=%s",
                l0_node_id,
                len(text),
                len(str(node.get("l1_summary") or "")),
            )
        return

    l2 = (raw_l2 or "").strip().replace("\n", " ")
    max_l2 = ma_int("MULTI_AGENT_CONTEXT_GRAPH_L2_MAX_CHARS", 400)
    node["l2_one_liner"] = l2[:max_l2]
    node["compression_at"] = datetime.now(timezone.utc).isoformat()
    _emit = pipeline_context.get("_trace_event")
    if callable(_emit):
        _emit(
            event="context_graph_llm_compressed",
            phase="context_graph",
            details={
                "l0_node_id": l0_node_id,
                "l0_chars": len(text),
                "l1_chars": len(str(node.get("l1_summary") or "")),
                "l2_chars": len(l2[:max_l2]),
                "partial": False,
            },
        )
    if ma_bool("MULTI_AGENT_CONTEXT_EXPAND_COMPACT_LOG", False):
        logger.info(
            "[context_graph_compress] node=%s l0=%s l1=%s l2=%s",
            l0_node_id,
            len(text),
            len(str(node.get("l1_summary") or "")),
            len(l2[:max_l2]),
        )
