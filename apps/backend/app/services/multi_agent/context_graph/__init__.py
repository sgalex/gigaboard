"""
Иерархический контекстный граф (shared memory) для Multi-Agent.

Этап 1–2: хранилище в pipeline_context + ingest узлов L0 после каждого шага.
См. docs/CONTEXT_ENGINEERING.md (контекстный пайплайн).
"""

from .compression import maybe_compress_l0_node_with_llm, resolve_slice_node_body
from .constants import CONTEXT_GRAPH_COMPRESSION_AGENT_KEY
from .ingest import ingest_agent_result_dict
from .slice import build_context_graph_slice
from .store import ensure_context_graph, init_context_graph

__all__ = [
    "CONTEXT_GRAPH_COMPRESSION_AGENT_KEY",
    "build_context_graph_slice",
    "ensure_context_graph",
    "init_context_graph",
    "ingest_agent_result_dict",
    "maybe_compress_l0_node_with_llm",
    "resolve_slice_node_body",
]
