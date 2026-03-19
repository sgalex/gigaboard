"""ContextExecutionService — deterministic data preparation for AI assistant context.

MVP scope:
- Works with pre-built board context payload (content_nodes_data/table_catalog).
- Selects relevant tables by selected nodes and explicit required table names.
- Optionally applies query filter expression to table sample rows.
"""
from __future__ import annotations

from copy import deepcopy
from difflib import SequenceMatcher
import json
import logging
import re
from typing import Any
from uuid import UUID
from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content_node import ContentNode
from app.services.content_node_service import ContentNodeService
from app.services.dimension_service import DimensionService
from app.services.filter_engine import FilterEngine
from app.services.source_node_service import SourceNodeService

logger = logging.getLogger(__name__)


class ContextExecutionService:
    """Prepares compact, deterministic context payload for assistant pipelines."""

    MAX_PREPARED_NODES = 20
    MAX_PREPARED_TABLES_PER_NODE = 4
    MAX_PREPARED_ROWS_PER_TABLE = 8
    MAX_CATALOG_NODES = 40
    MAX_CATALOG_TABLES_PER_NODE = 6
    MAX_CATALOG_ROWS_PER_TABLE = 1
    MAX_WORKING_SET_TABLES_TOTAL = 10

    async def prepare_board_context(
        self,
        board_context: dict[str, Any],
        *,
        db: AsyncSession | None = None,
        board_id: UUID | None = None,
        source_board_ids: list[str] | None = None,
        selected_node_ids: list[str] | None = None,
        required_tables: list[str] | None = None,
        user_message: str | None = None,
        filter_expression: dict[str, Any] | None = None,
        allow_auto_filter: bool = False,
    ) -> dict[str, Any]:
        """Prepare board-scoped data for LLM and return transparent context_used."""
        all_nodes_data = board_context.get("content_nodes_data", []) or []
        selected_set = {str(nid) for nid in (selected_node_ids or [])}
        auto_filter_planned = False
        auto_filter_reason: str | None = None

        required_tables_lower = {
            str(name).lower()
            for name in (required_tables or [])
            if name
        }

        catalog_nodes = self._build_catalog_nodes(all_nodes_data)
        prepared_nodes = self._build_working_set_nodes(
            nodes=all_nodes_data,
            selected_set=selected_set,
            required_tables=required_tables_lower,
            user_message=user_message or "",
        )

        # Auto-plan cross-filter from user question for factual/entity queries.
        if not filter_expression and prepared_nodes:
            planned_filter = self._plan_filter_expression_from_query(
                user_message=user_message or "",
                prepared_nodes=prepared_nodes,
            )
            if planned_filter:
                filter_expression = planned_filter
                allow_auto_filter = True
                auto_filter_planned = True
                auto_filter_reason = "query_entity_match"
                logger.info("🧩 ContextExecutionService auto-planned filter: %s", planned_filter)

        context_used: dict[str, Any] = {
            "scope": "board",
            "tables": [],
            "catalog": {
                "nodes": len(catalog_nodes),
                "tables": self._count_tables(catalog_nodes),
                "rows_per_table": self.MAX_CATALOG_ROWS_PER_TABLE,
            },
            "working_set": {
                "nodes": len(prepared_nodes),
                "tables": self._count_tables(prepared_nodes),
                "rows_per_table": self.MAX_PREPARED_ROWS_PER_TABLE,
            },
            "filters": filter_expression if filter_expression and allow_auto_filter else None,
            "proposed_filters": filter_expression if filter_expression and not allow_auto_filter else None,
            "filter_applied_for_answer": False,
            "auto_filter_planned": auto_filter_planned,
            "auto_filter_reason": auto_filter_reason,
            "filtering_mode": "none",
            "resolved_source_board_ids": [],
        }

        source_board_uuid_list: list[UUID] = []
        for raw_bid in source_board_ids or []:
            try:
                source_board_uuid_list.append(UUID(str(raw_bid)))
            except Exception:
                continue
        # Deduplicate while preserving order.
        dedup_source_board_ids: list[UUID] = []
        seen_source_boards: set[str] = set()
        for bid in source_board_uuid_list:
            key = str(bid)
            if key in seen_source_boards:
                continue
            seen_source_boards.add(key)
            dedup_source_board_ids.append(bid)

        # Fallback for dashboard-like payloads where source_board_ids are absent:
        # infer board set directly from real content-node UUIDs in prepared context.
        if filter_expression and allow_auto_filter and db is not None and not dedup_source_board_ids:
            inferred_board_ids = await self._infer_source_board_ids_from_prepared_nodes(
                db=db,
                prepared_nodes=prepared_nodes,
            )
            if inferred_board_ids:
                dedup_source_board_ids = inferred_board_ids
        context_used["resolved_source_board_ids"] = [str(v) for v in dedup_source_board_ids]

        if (
            filter_expression
            and allow_auto_filter
            and db is not None
            and dedup_source_board_ids
        ):
            # Dashboard path: filter across all source boards used by this dashboard.
            full_filtered = await self._prepare_with_multi_board_filtering(
                db=db,
                source_board_ids=dedup_source_board_ids,
                prepared_nodes=prepared_nodes,
                filter_expression=filter_expression,
            )
            prepared_nodes = full_filtered["prepared_nodes_data"]
            context_used["tables"] = full_filtered["table_stats"]
            context_used["filter_applied_for_answer"] = True
            context_used["filtering_mode"] = "multi_board_full"
        elif filter_expression and allow_auto_filter and db is not None and board_id is not None:
            # Prefer full-data filtering path to report exact row_count_before/after.
            full_filtered = await self._prepare_with_full_data_filtering(
                db=db,
                board_id=board_id,
                prepared_nodes=prepared_nodes,
                filter_expression=filter_expression,
            )
            prepared_nodes = full_filtered["prepared_nodes_data"]
            context_used["tables"] = full_filtered["table_stats"]
            context_used["filter_applied_for_answer"] = True
            context_used["filtering_mode"] = "single_board_full"
        elif filter_expression and allow_auto_filter and db is not None:
            # Dashboard fallback: try full rows by node IDs even without board_id.
            full_filtered = await self._prepare_with_node_ids_full_filtering(
                db=db,
                prepared_nodes=prepared_nodes,
                filter_expression=filter_expression,
            )
            prepared_nodes = full_filtered["prepared_nodes_data"]
            context_used["tables"] = full_filtered["table_stats"]
            context_used["filter_applied_for_answer"] = True
            context_used["filtering_mode"] = "node_ids_full"
        elif filter_expression and allow_auto_filter:
            # Fallback path (sample-only) when DB/board context is unavailable.
            for node in prepared_nodes:
                filtered_tables, table_stats = self._apply_filters_to_node_tables(
                    tables=node.get("tables", []),
                    filter_expression=filter_expression,
                )
                node["tables"] = filtered_tables
                context_used["tables"].extend(
                    {
                        "node_id": node.get("id"),
                        "node_name": node.get("name"),
                        **stats,
                    }
                    for stats in table_stats
                )
            context_used["filter_applied_for_answer"] = True
            context_used["filtering_mode"] = "sample_only"
        else:
            for node in prepared_nodes:
                for table in node.get("tables", []):
                    before_count = int(table.get("row_count", len(table.get("sample_rows", []))))
                    sample_count = len(table.get("sample_rows", []))
                    context_used["tables"].append({
                        "node_id": node.get("id"),
                        "node_name": node.get("name"),
                        "table_name": table.get("name", "table"),
                        "row_count_before": before_count,
                        "row_count_after": sample_count,
                        "row_count_after_is_sample": True,
                    })
            context_used["filtering_mode"] = "unfiltered_sample"

        return {
            "prepared_nodes_data": prepared_nodes,
            "catalog_nodes_data": catalog_nodes,
            "context_used": context_used,
        }

    @staticmethod
    def _count_tables(nodes: list[dict[str, Any]]) -> int:
        return sum(len(n.get("tables", []) or []) for n in nodes if isinstance(n, dict))

    def _build_catalog_nodes(self, nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """All tables, tiny payload for board-wide orientation."""
        catalog: list[dict[str, Any]] = []
        for node in nodes[: self.MAX_CATALOG_NODES]:
            raw_tables = node.get("tables", []) or []
            trimmed_tables = self._trim_tables_with_limit(
                raw_tables,
                self.MAX_CATALOG_ROWS_PER_TABLE,
                table_limit=self.MAX_CATALOG_TABLES_PER_NODE,
            )
            if not trimmed_tables:
                continue
            catalog.append({
                "id": node.get("id"),
                "name": node.get("name"),
                "node_type": node.get("node_type"),
                "text": node.get("text", ""),
                "tables": trimmed_tables,
            })
        return catalog

    def _build_working_set_nodes(
        self,
        *,
        nodes: list[dict[str, Any]],
        selected_set: set[str],
        required_tables: set[str],
        user_message: str,
    ) -> list[dict[str, Any]]:
        """Focused subset for active agent reasoning."""
        candidate_nodes = nodes
        if selected_set:
            selected_nodes = [n for n in nodes if str(n.get("id")) in selected_set]
            if selected_nodes:
                candidate_nodes = selected_nodes

        if required_tables:
            by_required = self._select_and_trim_nodes_with_required_tables(
                nodes=candidate_nodes,
                required_tables=required_tables,
            )
            if by_required:
                # Keep required tables first, but do not over-prune context to only them:
                # add relevant extras so multi-step queries can still use companion tables.
                ranked = self._select_by_query_relevance(candidate_nodes, user_message)
                if ranked:
                    merged = self._merge_working_set_nodes(
                        primary=by_required,
                        secondary=ranked,
                    )
                    return self._limit_working_set_tables(merged)
                return self._limit_working_set_tables(by_required)

        ranked = self._select_by_query_relevance(candidate_nodes, user_message)
        if ranked:
            return self._limit_working_set_tables(ranked)

        fallback = self._select_and_trim_nodes(
            nodes=candidate_nodes,
            required_tables=set(),
        )
        return self._limit_working_set_tables(fallback)

    def _select_by_query_relevance(
        self,
        nodes: list[dict[str, Any]],
        user_message: str,
    ) -> list[dict[str, Any]]:
        """Rank tables by lexical overlap with the user query."""
        tokens = self._query_tokens(user_message)
        if not tokens:
            return []

        scored: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
        for node in nodes[: self.MAX_PREPARED_NODES]:
            node_name = str(node.get("name", ""))
            for table in (node.get("tables", []) or []):
                table_name = str(table.get("name", "table"))
                haystack = f"{node_name} {table_name} {self._columns_text(table.get('columns', []))}".lower()
                score = sum(1 for t in tokens if t in haystack)
                if score > 0:
                    scored.append((score, node, table))

        if not scored:
            return []

        scored.sort(key=lambda x: x[0], reverse=True)
        selected_pairs = scored[: self.MAX_WORKING_SET_TABLES_TOTAL]
        by_node: dict[str, dict[str, Any]] = {}

        for _, node, table in selected_pairs:
            node_id = str(node.get("id"))
            entry = by_node.get(node_id)
            if not entry:
                entry = {
                    "id": node.get("id"),
                    "name": node.get("name"),
                    "node_type": node.get("node_type"),
                    "text": node.get("text", ""),
                    "tables": [],
                }
                by_node[node_id] = entry
            entry["tables"].append(deepcopy(table))

        prepared = list(by_node.values())
        for node in prepared:
            node["tables"] = self._trim_tables(node.get("tables", []))
        return prepared

    @staticmethod
    def _query_tokens(user_message: str) -> list[str]:
        parts = re.split(r"[\s_\-.,:;!?()]+", (user_message or "").lower())
        return [p for p in parts if len(p) >= 3]

    @staticmethod
    def _columns_text(columns: list[Any]) -> str:
        names: list[str] = []
        for col in columns if isinstance(columns, list) else []:
            if isinstance(col, dict):
                names.append(str(col.get("name", "")))
            else:
                names.append(str(col))
        return " ".join(names)

    def _limit_working_set_tables(
        self,
        nodes: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Hard cap total working-set tables across all nodes."""
        remaining = self.MAX_WORKING_SET_TABLES_TOTAL
        limited: list[dict[str, Any]] = []
        for node in nodes:
            if remaining <= 0:
                break
            tables = node.get("tables", []) or []
            if not tables:
                continue
            take = tables[:remaining]
            remaining -= len(take)
            limited.append({
                "id": node.get("id"),
                "name": node.get("name"),
                "node_type": node.get("node_type"),
                "text": node.get("text", ""),
                "tables": take,
            })
        return limited

    @staticmethod
    def _merge_working_set_nodes(
        *,
        primary: list[dict[str, Any]],
        secondary: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Merge two working sets preserving order and avoiding duplicate node/table pairs.
        """
        out: list[dict[str, Any]] = []
        by_node: dict[str, dict[str, Any]] = {}
        seen_pairs: set[tuple[str, str]] = set()

        def _append(nodes: list[dict[str, Any]]) -> None:
            for node in nodes or []:
                node_id = str(node.get("id"))
                entry = by_node.get(node_id)
                if not entry:
                    entry = {
                        "id": node.get("id"),
                        "name": node.get("name"),
                        "node_type": node.get("node_type"),
                        "text": node.get("text", ""),
                        "tables": [],
                    }
                    by_node[node_id] = entry
                    out.append(entry)

                for table in node.get("tables", []) or []:
                    table_name = str(table.get("name", "table"))
                    key = (node_id, table_name)
                    if key in seen_pairs:
                        continue
                    seen_pairs.add(key)
                    entry["tables"].append(deepcopy(table))

        _append(primary)
        _append(secondary)
        return out

    async def _prepare_with_full_data_filtering(
        self,
        *,
        db: AsyncSession,
        board_id: UUID,
        prepared_nodes: list[dict[str, Any]],
        filter_expression: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply filter expression to full table rows from DB and keep compact samples."""
        # IMPORTANT: this method may run inside a request transaction that has pending writes
        # (e.g. chat_messages insert). Disable autoflush to avoid unrelated FK errors.
        with db.no_autoflush:
            full_tables_by_node = await self._get_full_tables_by_node(db=db, board_id=board_id)
            mappings_by_node = await self._get_mappings_by_node(db=db, board_id=board_id)

        output_nodes: list[dict[str, Any]] = []
        table_stats: list[dict[str, Any]] = []

        for node in prepared_nodes:
            node_id = str(node.get("id"))
            node_full_tables = full_tables_by_node.get(node_id, {})
            node_mappings = mappings_by_node.get(node_id, [])

            out_tables: list[dict[str, Any]] = []
            for table in node.get("tables", []):
                table_name = str(table.get("name", "table"))
                source_table = self._resolve_source_table(node_full_tables, table_name)
                used_sample_fallback = source_table is None
                if not source_table:
                    source_table = {
                        "name": table_name,
                        "columns": table.get("columns", []),
                        "rows": table.get("sample_rows", []),
                        "row_count": len(table.get("sample_rows", [])),
                    }

                table_mappings = [
                    m for m in node_mappings
                    if m.get("table_name") == table_name
                ]
                if not table_mappings:
                    # Fallback: if board dimension mappings are missing for table,
                    # use identity mapping by column names.
                    table_columns = source_table.get("columns", []) or []
                    table_mappings = [
                        {
                            "table_name": table_name,
                            "column_name": c.get("name") if isinstance(c, dict) else str(c),
                            "dim_name": c.get("name") if isinstance(c, dict) else str(c),
                        }
                        for c in table_columns
                        if (c.get("name") if isinstance(c, dict) else str(c))
                    ]
                filtered = FilterEngine.apply_filters(
                    [source_table],
                    filter_expression,
                    table_mappings,
                )
                filtered_table = filtered[0] if filtered else source_table
                filtered_rows = filtered_table.get("rows", [])

                out_table = deepcopy(table)
                out_table["sample_rows"] = filtered_rows[: self.MAX_PREPARED_ROWS_PER_TABLE]
                out_table["row_count"] = len(filtered_rows)
                out_tables.append(out_table)

                before_count = int(
                    source_table.get("row_count", len(source_table.get("rows", [])))
                )
                table_stats.append({
                    "node_id": node_id,
                    "node_name": node.get("name"),
                    "table_name": table_name,
                    "row_count_before": before_count,
                    "row_count_after": len(filtered_rows),
                    "row_count_after_is_sample": used_sample_fallback,
                })
                self._log_filtered_table_trace(
                    filtering_mode="single_board_full",
                    node_id=node_id,
                    node_name=str(node.get("name", "")),
                    table_name=table_name,
                    resolved_table_name=str(source_table.get("name", table_name)),
                    filter_expression=filter_expression,
                    table_mappings=table_mappings,
                    before_rows=source_table.get("rows", []) or [],
                    after_rows=filtered_rows,
                    used_sample_fallback=used_sample_fallback,
                )

            output_nodes.append({
                "id": node.get("id"),
                "name": node.get("name"),
                "node_type": node.get("node_type"),
                "text": node.get("text", ""),
                "tables": out_tables,
            })

        return {
            "prepared_nodes_data": output_nodes,
            "table_stats": table_stats,
        }

    async def _prepare_with_node_ids_full_filtering(
        self,
        *,
        db: AsyncSession,
        prepared_nodes: list[dict[str, Any]],
        filter_expression: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Apply filter expression to full rows fetched by content node IDs.
        Used as fallback for dashboard scope when source board_id is unknown.
        """
        node_uuids: list[UUID] = []
        for node in prepared_nodes:
            raw_id = str(node.get("id", "")).strip()
            if not raw_id or ":" in raw_id:
                continue
            try:
                node_uuids.append(UUID(raw_id))
            except Exception:
                continue

        full_tables_by_node: dict[str, dict[str, dict[str, Any]]] = {}
        if node_uuids:
            result = await db.execute(
                select(ContentNode).where(ContentNode.id.in_(node_uuids))
            )
            for content_node in result.scalars().all():
                node_id = str(content_node.id)
                node_content = content_node.content if isinstance(content_node.content, dict) else {}
                tables = node_content.get("tables", []) if isinstance(node_content, dict) else []
                table_map: dict[str, dict[str, Any]] = {}
                for table in tables if isinstance(tables, list) else []:
                    if not isinstance(table, dict):
                        continue
                    tname = str(table.get("name", "table"))
                    rows = table.get("rows", []) or []
                    table_map[tname] = {
                        "name": tname,
                        "columns": table.get("columns", []) or [],
                        "rows": rows,
                        "row_count": int(table.get("row_count", len(rows))),
                    }
                full_tables_by_node[node_id] = table_map

        output_nodes: list[dict[str, Any]] = []
        table_stats: list[dict[str, Any]] = []

        for node in prepared_nodes:
            node_id = str(node.get("id"))
            node_full_tables = full_tables_by_node.get(node_id, {})
            out_tables: list[dict[str, Any]] = []

            for table in node.get("tables", []) or []:
                table_name = str(table.get("name", "table"))
                source_table = self._resolve_source_table(node_full_tables, table_name)
                used_sample_fallback = source_table is None
                if not source_table:
                    source_table = {
                        "name": table_name,
                        "columns": table.get("columns", []) or [],
                        "rows": table.get("sample_rows", []) or [],
                        "row_count": int(table.get("row_count", len(table.get("sample_rows", []) or []))),
                    }

                table_columns = source_table.get("columns", []) or []
                table_mappings = [
                    {
                        "table_name": table_name,
                        "column_name": c.get("name") if isinstance(c, dict) else str(c),
                        "dim_name": c.get("name") if isinstance(c, dict) else str(c),
                    }
                    for c in table_columns
                    if (c.get("name") if isinstance(c, dict) else str(c))
                ]

                filtered = FilterEngine.apply_filters(
                    [source_table],
                    filter_expression,
                    table_mappings,
                )
                filtered_table = filtered[0] if filtered else source_table
                filtered_rows = filtered_table.get("rows", []) or []

                out_table = deepcopy(table)
                out_table["sample_rows"] = filtered_rows[: self.MAX_PREPARED_ROWS_PER_TABLE]
                out_table["row_count"] = len(filtered_rows)
                out_tables.append(out_table)

                before_count = int(source_table.get("row_count", len(source_table.get("rows", []) or [])))
                table_stats.append({
                    "node_id": node_id,
                    "node_name": node.get("name"),
                    "table_name": table_name,
                    "row_count_before": before_count,
                    "row_count_after": len(filtered_rows),
                    "row_count_after_is_sample": used_sample_fallback,
                })
                self._log_filtered_table_trace(
                    filtering_mode="node_ids_full",
                    node_id=node_id,
                    node_name=str(node.get("name", "")),
                    table_name=table_name,
                    resolved_table_name=str(source_table.get("name", table_name)),
                    filter_expression=filter_expression,
                    table_mappings=table_mappings,
                    before_rows=source_table.get("rows", []) or [],
                    after_rows=filtered_rows,
                    used_sample_fallback=used_sample_fallback,
                )

            output_nodes.append({
                "id": node.get("id"),
                "name": node.get("name"),
                "node_type": node.get("node_type"),
                "text": node.get("text", ""),
                "tables": out_tables,
            })

        return {
            "prepared_nodes_data": output_nodes,
            "table_stats": table_stats,
        }

    async def _prepare_with_multi_board_filtering(
        self,
        *,
        db: AsyncSession,
        source_board_ids: list[UUID],
        prepared_nodes: list[dict[str, Any]],
        filter_expression: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Apply filter expression using full rows/mappings aggregated from multiple boards.
        Designed for dashboard contexts that combine nodes from different source boards.
        """
        with db.no_autoflush:
            full_tables_by_node = await self._get_full_tables_by_board_ids(
                db=db,
                board_ids=source_board_ids,
            )
            mappings_by_node = await self._get_mappings_by_board_ids(
                db=db,
                board_ids=source_board_ids,
            )

        output_nodes: list[dict[str, Any]] = []
        table_stats: list[dict[str, Any]] = []

        for node in prepared_nodes:
            node_id = str(node.get("id"))
            node_full_tables = full_tables_by_node.get(node_id, {})
            node_mappings = mappings_by_node.get(node_id, [])
            out_tables: list[dict[str, Any]] = []

            for table in node.get("tables", []):
                table_name = str(table.get("name", "table"))
                source_table = self._resolve_source_table(node_full_tables, table_name)
                used_sample_fallback = source_table is None
                if not source_table:
                    source_table = {
                        "name": table_name,
                        "columns": table.get("columns", []),
                        "rows": table.get("sample_rows", []),
                        "row_count": len(table.get("sample_rows", [])),
                    }

                table_mappings = [
                    m for m in node_mappings
                    if m.get("table_name") == table_name
                ]
                if not table_mappings:
                    table_columns = source_table.get("columns", []) or []
                    table_mappings = [
                        {
                            "table_name": table_name,
                            "column_name": c.get("name") if isinstance(c, dict) else str(c),
                            "dim_name": c.get("name") if isinstance(c, dict) else str(c),
                        }
                        for c in table_columns
                        if (c.get("name") if isinstance(c, dict) else str(c))
                    ]

                filtered = FilterEngine.apply_filters(
                    [source_table],
                    filter_expression,
                    table_mappings,
                )
                filtered_table = filtered[0] if filtered else source_table
                filtered_rows = filtered_table.get("rows", [])

                out_table = deepcopy(table)
                out_table["sample_rows"] = filtered_rows[: self.MAX_PREPARED_ROWS_PER_TABLE]
                out_table["row_count"] = len(filtered_rows)
                out_tables.append(out_table)

                before_count = int(
                    source_table.get("row_count", len(source_table.get("rows", [])))
                )
                table_stats.append({
                    "node_id": node_id,
                    "node_name": node.get("name"),
                    "table_name": table_name,
                    "row_count_before": before_count,
                    "row_count_after": len(filtered_rows),
                    "row_count_after_is_sample": used_sample_fallback,
                })
                self._log_filtered_table_trace(
                    filtering_mode="multi_board_full",
                    node_id=node_id,
                    node_name=str(node.get("name", "")),
                    table_name=table_name,
                    resolved_table_name=str(source_table.get("name", table_name)),
                    filter_expression=filter_expression,
                    table_mappings=table_mappings,
                    before_rows=source_table.get("rows", []) or [],
                    after_rows=filtered_rows,
                    used_sample_fallback=used_sample_fallback,
                )

            output_nodes.append({
                "id": node.get("id"),
                "name": node.get("name"),
                "node_type": node.get("node_type"),
                "text": node.get("text", ""),
                "tables": out_tables,
            })

        return {
            "prepared_nodes_data": output_nodes,
            "table_stats": table_stats,
        }

    def _select_and_trim_nodes(
        self,
        *,
        nodes: list[dict[str, Any]],
        required_tables: set[str],
    ) -> list[dict[str, Any]]:
        if required_tables:
            prepared_filtered = self._select_and_trim_nodes_with_required_tables(
                nodes=nodes,
                required_tables=required_tables,
            )
            if prepared_filtered:
                return prepared_filtered

        prepared: list[dict[str, Any]] = []
        for node in nodes[: self.MAX_PREPARED_NODES]:
            raw_tables = node.get("tables", []) or []
            selected_tables = raw_tables[: self.MAX_PREPARED_TABLES_PER_NODE]
            trimmed_tables = self._trim_tables(selected_tables)
            if not trimmed_tables:
                continue
            prepared.append({
                "id": node.get("id"),
                "name": node.get("name"),
                "node_type": node.get("node_type"),
                "text": node.get("text", ""),
                "tables": trimmed_tables,
            })
        return prepared

    def _select_and_trim_nodes_with_required_tables(
        self,
        *,
        nodes: list[dict[str, Any]],
        required_tables: set[str],
    ) -> list[dict[str, Any]]:
        """Select only explicitly requested tables (with robust name matching)."""
        prepared: list[dict[str, Any]] = []

        for node in nodes[: self.MAX_PREPARED_NODES]:
            raw_tables = node.get("tables", []) or []
            selected_tables: list[dict[str, Any]] = []
            for table in raw_tables:
                table_name = str(table.get("name", "table"))
                if self._table_matches_required(table_name, required_tables):
                    selected_tables.append(table)

            trimmed_tables = self._trim_tables(selected_tables[: self.MAX_PREPARED_TABLES_PER_NODE])
            if not trimmed_tables:
                continue

            prepared.append({
                "id": node.get("id"),
                "name": node.get("name"),
                "node_type": node.get("node_type"),
                "text": node.get("text", ""),
                "tables": trimmed_tables,
            })

        return prepared

    def _trim_tables(self, tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return self._trim_tables_with_limit(
            tables,
            self.MAX_PREPARED_ROWS_PER_TABLE,
        )

    def _trim_tables_with_limit(
        self,
        tables: list[dict[str, Any]],
        sample_rows_limit: int,
        *,
        table_limit: int | None = None,
    ) -> list[dict[str, Any]]:
        trimmed_tables: list[dict[str, Any]] = []
        max_tables = table_limit if isinstance(table_limit, int) and table_limit > 0 else self.MAX_PREPARED_TABLES_PER_NODE
        for table in tables[: max_tables]:
            t_copy = deepcopy(table)
            sample_rows = t_copy.get("sample_rows", [])
            if isinstance(sample_rows, list):
                t_copy["sample_rows"] = sample_rows[: sample_rows_limit]
            trimmed_tables.append(t_copy)
        return trimmed_tables

    @staticmethod
    def _table_matches_required(table_name: str, required_tables: set[str]) -> bool:
        table_candidates = ContextExecutionService._name_candidates(table_name)
        for req in required_tables:
            if table_candidates & ContextExecutionService._name_candidates(req):
                return True
        return False

    @staticmethod
    def _resolve_source_table(
        table_map: dict[str, dict[str, Any]],
        requested_name: str,
    ) -> dict[str, Any] | None:
        """
        Resolve source table by exact or normalized name variants.
        Helps when preview/table catalog uses names like node:table vs table.
        """
        if not table_map:
            return None
        direct = table_map.get(requested_name)
        if direct:
            return direct
        requested_candidates = ContextExecutionService._name_candidates(requested_name)
        for key, value in table_map.items():
            if requested_candidates & ContextExecutionService._name_candidates(key):
                return value
        return None

    @staticmethod
    def _row_compact(row: Any, *, max_fields: int = 8) -> dict[str, Any]:
        if not isinstance(row, dict):
            return {}
        out: dict[str, Any] = {}
        for i, (k, v) in enumerate(row.items()):
            if i >= max_fields:
                break
            out[str(k)] = v
        return out

    @staticmethod
    def _mapping_compact(table_mappings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        compact: list[dict[str, Any]] = []
        for m in table_mappings[:20]:
            if not isinstance(m, dict):
                continue
            compact.append({
                "dim_name": m.get("dim_name"),
                "column_name": m.get("column_name"),
                "table_name": m.get("table_name"),
            })
        return compact

    def _log_filtered_table_trace(
        self,
        *,
        filtering_mode: str,
        node_id: str,
        node_name: str,
        table_name: str,
        resolved_table_name: str,
        filter_expression: dict[str, Any],
        table_mappings: list[dict[str, Any]],
        before_rows: list[dict[str, Any]],
        after_rows: list[dict[str, Any]],
        used_sample_fallback: bool,
    ) -> None:
        """
        Verbose, structured trace for filter diagnostics (per table).
        """
        try:
            trace_payload = {
                "event": "context_filter_table_trace",
                "mode": filtering_mode,
                "node_id": node_id,
                "node_name": node_name,
                "table_name": table_name,
                "resolved_table_name": resolved_table_name,
                "used_sample_fallback": bool(used_sample_fallback),
                "before_count": len(before_rows or []),
                "after_count": len(after_rows or []),
                "filter_expression": filter_expression,
                "mappings": self._mapping_compact(table_mappings),
                "before_sample": [
                    self._row_compact(r) for r in (before_rows or [])[:3]
                    if isinstance(r, dict)
                ],
                "after_sample": [
                    self._row_compact(r) for r in (after_rows or [])[:3]
                    if isinstance(r, dict)
                ],
            }
            logger.info("🔎 FILTER TRACE %s", json.dumps(trace_payload, ensure_ascii=False, default=str))
        except Exception:
            logger.exception("Failed to emit filter trace log for %s.%s", node_id, table_name)

    @staticmethod
    def _name_candidates(value: str) -> set[str]:
        """Generate comparable name variants for robust required_tables matching."""
        lower = str(value).strip().lower()
        if not lower:
            return set()

        parts_dot = [p for p in lower.split(".") if p]
        parts_colon = [p for p in lower.split(":") if p]
        parts_slash = [p for p in lower.split("/") if p]

        candidates = {lower}
        if parts_dot:
            candidates.add(parts_dot[-1])
        if parts_colon:
            candidates.add(parts_colon[-1])
        if parts_slash:
            candidates.add(parts_slash[-1])
        return candidates

    def _apply_filters_to_node_tables(
        self,
        *,
        tables: list[dict[str, Any]],
        filter_expression: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        transformed: list[dict[str, Any]] = []
        stats: list[dict[str, Any]] = []

        for table in tables:
            columns = table.get("columns", []) or []
            sample_rows = table.get("sample_rows", []) or []

            filterable_table = {
                "name": table.get("name", "table"),
                "columns": columns,
                "rows": sample_rows,
                "row_count": len(sample_rows),
            }
            mappings = []
            for col in columns:
                col_name = col.get("name") if isinstance(col, dict) else str(col)
                if not col_name:
                    continue
                mappings.append({
                    "table_name": filterable_table["name"],
                    "column_name": col_name,
                    "dim_name": col_name,
                })

            filtered_tables = FilterEngine.apply_filters(
                [filterable_table],
                filter_expression,
                mappings,
            )
            filtered_table = filtered_tables[0] if filtered_tables else filterable_table
            filtered_rows = filtered_table.get("rows", [])

            out_table = deepcopy(table)
            out_table["sample_rows"] = filtered_rows[: self.MAX_PREPARED_ROWS_PER_TABLE]
            transformed.append(out_table)

            before_count = int(table.get("row_count", len(sample_rows)))
            stats.append({
                "table_name": table.get("name", "table"),
                "row_count_before": before_count,
                "row_count_after": len(filtered_rows),
                "row_count_after_is_sample": True,
            })

        return transformed, stats

    def _plan_filter_expression_from_query(
        self,
        *,
        user_message: str,
        prepared_nodes: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """
        Build simple FilterExpression for brand/manufacturer-like queries.

        Example output:
            {"type":"condition","dim":"brand","op":"contains","value":"Philips"}
        """
        query = (user_message or "").strip()
        if not query:
            return None

        q_lower = query.lower()
        if not any(k in q_lower for k in ("бренд", "товар", "ходов", "продаж", "product", "brand", "manufacturer")):
            return None

        candidates = self._extract_entity_candidates(query)
        if not candidates:
            return None

        dim_hints = {
            "brand", "manufacturer", "vendor", "brand_name", "producer",
            "бренд", "марка", "производитель",
        }

        # Try exact value match in sample rows for brand-like columns.
        for node in prepared_nodes:
            for table in node.get("tables", []) or []:
                columns = table.get("columns", []) or []
                sample_rows = table.get("sample_rows", []) or []
                column_names = [
                    (c.get("name") if isinstance(c, dict) else str(c))
                    for c in columns
                ]
                for col in column_names:
                    col_l = (col or "").lower()
                    if not col_l or not any(h in col_l for h in dim_hints):
                        continue
                    for row in sample_rows if isinstance(sample_rows, list) else []:
                        raw = row.get(col) if isinstance(row, dict) else None
                        if raw is None:
                            continue
                        raw_s = str(raw).strip()
                        raw_l = raw_s.lower()
                        for cand in candidates:
                            cand_l = cand.lower()
                            if cand_l == raw_l or cand_l in raw_l or raw_l in cand_l:
                                return {
                                    "type": "condition",
                                    "dim": col,
                                    "op": "contains",
                                    "value": raw_s,
                                }
                            # Typo-tolerant entity matching (e.g., "Phillips" -> "Philips").
                            ratio = SequenceMatcher(None, cand_l, raw_l).ratio()
                            if ratio >= 0.84:
                                return {
                                    "type": "condition",
                                    "dim": col,
                                    "op": "contains",
                                    "value": raw_s,
                                }

        # Fallback: use first entity and first suitable dimension-like column.
        for node in prepared_nodes:
            for table in node.get("tables", []) or []:
                columns = table.get("columns", []) or []
                for c in columns:
                    col = c.get("name") if isinstance(c, dict) else str(c)
                    col_l = (col or "").lower()
                    if col_l and any(h in col_l for h in dim_hints):
                        return {
                            "type": "condition",
                            "dim": col,
                            "op": "contains",
                            "value": candidates[0],
                        }

        return None

    @staticmethod
    def _extract_entity_candidates(query: str) -> list[str]:
        """
        Extract likely entity tokens from natural-language question.
        Keeps mixed-case latin/cyrillic words and phrase after 'у/for/of'.
        """
        out: list[str] = []
        q = query.strip()

        # Patterns: "у Philips", "for Philips", "of Philips"
        for pat in (
            r"\bу\s+([A-Za-zА-Яа-я0-9][A-Za-zА-Яа-я0-9\-\._]{1,40})",
            r"\bfor\s+([A-Za-z0-9][A-Za-z0-9\-\._]{1,40})",
            r"\bof\s+([A-Za-z0-9][A-Za-z0-9\-\._]{1,40})",
        ):
            m = re.search(pat, q, flags=re.IGNORECASE)
            if m:
                out.append(m.group(1))

        # Additional title-case / latin tokens.
        tokens = re.findall(r"[A-Za-zА-Яа-я0-9][A-Za-zА-Яа-я0-9\-\._]{2,40}", q)
        stop = {"какой", "самый", "ходовой", "товар", "бренд", "product", "brand"}
        for t in tokens:
            if t.lower() in stop:
                continue
            if any(ch.isalpha() for ch in t):
                out.append(t)

        # Deduplicate preserving order.
        dedup: list[str] = []
        seen: set[str] = set()
        for v in out:
            key = v.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            dedup.append(v.strip())
        return dedup[:5]

    @staticmethod
    async def _get_full_tables_by_node(
        *,
        db: AsyncSession,
        board_id: UUID,
    ) -> dict[str, dict[str, dict[str, Any]]]:
        """Load full table payloads for all board data nodes."""
        sources = await SourceNodeService.get_board_sources(db, board_id)
        contents = await ContentNodeService.get_board_contents(db, board_id)
        by_node: dict[str, dict[str, dict[str, Any]]] = {}

        for node in sources + contents:
            node_id = str(node.id)
            tables = (node.content or {}).get("tables", []) if getattr(node, "content", None) else []
            table_map: dict[str, dict[str, Any]] = {}
            for table in tables:
                tname = str(table.get("name", "table"))
                columns = table.get("columns", [])
                rows = table.get("rows", [])
                table_map[tname] = {
                    "name": tname,
                    "columns": columns,
                    "rows": rows,
                    "row_count": table.get("row_count", len(rows)),
                }
            by_node[node_id] = table_map
        return by_node

    @staticmethod
    async def _get_mappings_by_node(
        *,
        db: AsyncSession,
        board_id: UUID,
    ) -> dict[str, list[dict[str, Any]]]:
        """Load dimension mappings for all board nodes."""
        return await DimensionService.get_all_mappings_for_board(db, board_id)

    @staticmethod
    async def _get_full_tables_by_board_ids(
        *,
        db: AsyncSession,
        board_ids: list[UUID],
    ) -> dict[str, dict[str, dict[str, Any]]]:
        """Load full table payloads for nodes across multiple boards."""
        by_node: dict[str, dict[str, dict[str, Any]]] = {}
        for board_id in board_ids:
            board_tables = await ContextExecutionService._get_full_tables_by_node(
                db=db,
                board_id=board_id,
            )
            by_node.update(board_tables)
        return by_node

    @staticmethod
    async def _get_mappings_by_board_ids(
        *,
        db: AsyncSession,
        board_ids: list[UUID],
    ) -> dict[str, list[dict[str, Any]]]:
        """Load and merge dimension mappings for nodes across multiple boards."""
        out: dict[str, list[dict[str, Any]]] = {}
        for board_id in board_ids:
            part = await DimensionService.get_all_mappings_for_board(db, board_id)
            for node_id, mappings in part.items():
                out.setdefault(node_id, []).extend(mappings or [])
        return out

    @staticmethod
    async def _infer_source_board_ids_from_prepared_nodes(
        *,
        db: AsyncSession,
        prepared_nodes: list[dict[str, Any]],
    ) -> list[UUID]:
        """
        Infer source board IDs from real ContentNode UUIDs in prepared nodes.
        Skips synthetic dashboard IDs like 'project_table:...'.
        """
        node_ids: list[UUID] = []
        for node in prepared_nodes:
            raw_id = str(node.get("id", "")).strip()
            if not raw_id or ":" in raw_id:
                continue
            try:
                node_ids.append(UUID(raw_id))
            except Exception:
                continue

        if not node_ids:
            return []

        result = await db.execute(
            select(ContentNode.id, ContentNode.board_id).where(ContentNode.id.in_(node_ids))
        )
        boards: list[UUID] = []
        seen: set[str] = set()
        for _nid, bid in result.all():
            if not bid:
                continue
            key = str(bid)
            if key in seen:
                continue
            seen.add(key)
            boards.append(bid)
        return boards

