"""Filters API routes — active filters for boards/dashboards and filter presets.

See docs/CROSS_FILTER_SYSTEM.md §5
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import get_db
from app.models import User
from app.middleware import get_current_user
from app.schemas.cross_filter import (
    ActiveFiltersUpdate,
    ActiveFiltersResponse,
    FilterExpression,
    FilterPresetCreate,
    FilterPresetUpdate,
    FilterPresetResponse,
    FilterStatsResponse,
    TableFilterStats,
)
from app.services.filter_preset_service import FilterPresetService

logger = logging.getLogger(__name__)

# In-memory store for active filters (Redis replacement for MVP).
# In production, replace with Redis: `board:{board_id}:user:{user_id}:filters`
_active_filters_store: dict[str, dict[str, Any]] = {}


def _filter_key(scope: str, target_id: str, user_id: str) -> str:
    return f"{scope}:{target_id}:{user_id}"


# ═══════════════════════════════════════════════════════════════════════
#  Board Filters
# ═══════════════════════════════════════════════════════════════════════

board_filter_router = APIRouter(
    prefix="/api/v1/boards/{board_id}/filters",
    tags=["filters"],
)


@board_filter_router.get("", response_model=ActiveFiltersResponse)
async def get_board_filters(
    board_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current active filters for a board."""
    key = _filter_key("board", str(board_id), str(current_user.id))
    data = _active_filters_store.get(key, {})
    return ActiveFiltersResponse(
        filters=data.get("filters"),
        preset_id=data.get("preset_id"),
        updated_at=data.get("updated_at"),
    )


@board_filter_router.put("", response_model=ActiveFiltersResponse)
async def set_board_filters(
    board_id: UUID,
    body: ActiveFiltersUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set (replace) active filters for a board."""
    from datetime import datetime

    key = _filter_key("board", str(board_id), str(current_user.id))
    filters_dict = None
    if body.filters is not None:
        filters_dict = body.filters.model_dump() if hasattr(body.filters, "model_dump") else body.filters
    _active_filters_store[key] = {
        "filters": filters_dict,
        "preset_id": None,
        "updated_at": datetime.utcnow(),
    }
    return ActiveFiltersResponse(**_active_filters_store[key])


@board_filter_router.post("/clear", response_model=ActiveFiltersResponse)
async def clear_board_filters(
    board_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Clear all active filters for a board."""
    key = _filter_key("board", str(board_id), str(current_user.id))
    _active_filters_store.pop(key, None)
    return ActiveFiltersResponse(filters=None, preset_id=None, updated_at=None)


@board_filter_router.post("/apply-preset/{preset_id}", response_model=ActiveFiltersResponse)
async def apply_board_preset(
    board_id: UUID,
    preset_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Apply a saved filter preset to this board."""
    from datetime import datetime

    preset = await FilterPresetService.get_preset(db, preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")
    key = _filter_key("board", str(board_id), str(current_user.id))
    _active_filters_store[key] = {
        "filters": preset.filters,
        "preset_id": str(preset.id),
        "updated_at": datetime.utcnow(),
    }
    return ActiveFiltersResponse(**_active_filters_store[key])


# ── Helper: проверяем есть ли в коде вызовы ai_resolve ──────────────────────

_AI_RESOLVE_RE = re.compile(r'\bgb\.ai_resolve_(?:batch|single)\b')


def _code_uses_ai(code: str | None) -> bool:
    return bool(code and _AI_RESOLVE_RE.search(code))


async def _compute_filtered_pipeline(
    db: AsyncSession,
    board_id: UUID,
    filters: FilterExpression | dict | None,
    user_id: str,
) -> dict[str, dict[str, Any]]:
    """Пересчитывает всю pandas-цепочку на доске с учётом фильтров.

    Алгоритм:
    1. Загружаем все SourceNode + ContentNode доски.
    2. Получаем все DimensionColumnMapping для доски одним запросом.
    3. Обрабатываем узлы в топологическом порядке (BFS по lineage.source_node_ids):
       - SourceNode: применяем FilterEngine к сырым строкам.
       - ContentNode без кода / с ai_resolve_*: FilterEngine к кэшированным строкам.
       - ContentNode с кодом (и без ai): перезапускаем код на отфильтрованных данных.
    4. Возвращаем {node_id: {tables, uses_ai, from_cache}} — НЕ пишем в БД.
    """
    from app.services.source_node_service import SourceNodeService
    from app.services.content_node_service import ContentNodeService
    from app.services.dimension_service import DimensionService
    from app.services.filter_engine import FilterEngine
    from app.services.executors.python_executor import python_executor

    # 1. Загрузка узлов
    source_nodes = await SourceNodeService.get_board_sources(db, board_id)
    content_nodes = await ContentNodeService.get_board_contents(db, board_id)

    # 2. Batch-загрузка маппингов
    all_mappings_by_node = await DimensionService.get_all_mappings_for_board(db, board_id)

    # 2a. Fallback: если маппинги отсутствуют, но есть фильтры — автодетектим
    if filters and not all_mappings_by_node:
        logger.info("_compute_filtered: no mappings found, running auto-detect for board %s", board_id)
        project_id = await DimensionService.get_project_id_for_node(db, board_id)
        if project_id:
            for sn in source_nodes:
                sn_tables = (sn.content or {}).get("tables", [])
                if sn_tables:
                    await DimensionService.auto_detect_and_upsert(db, project_id, sn.id, sn_tables)
            for cn in content_nodes:
                cn_tables = (cn.content or {}).get("tables", [])
                if cn_tables:
                    await DimensionService.auto_detect_and_upsert(db, project_id, cn.id, cn_tables)
            await db.flush()
            all_mappings_by_node = await DimensionService.get_all_mappings_for_board(db, board_id)

    logger.info(
        "_compute_filtered: board=%s sources=%d contents=%d filters=%s mappings_nodes=%d dim_names=%s",
        board_id,
        len(source_nodes),
        len(content_nodes),
        bool(filters),
        len(all_mappings_by_node),
        {m.get("dim_name") for maps in all_mappings_by_node.values() for m in maps} if all_mappings_by_node else set(),
    )

    # Быстрый lookup node по id
    node_by_id: dict[str, Any] = {}
    for n in source_nodes:
        node_by_id[str(n.id)] = n
    for n in content_nodes:
        # ContentNode и SourceNode могут иметь одинаковый ID, SourceNode приоритетнее
        if str(n.id) not in node_by_id:
            node_by_id[str(n.id)] = n

    # processed: node_id → уже посчитанные таблицы (list of table dicts)
    processed: dict[str, list[dict]] = {}
    result: dict[str, dict[str, Any]] = {}

    # ── Шаг 3a: SourceNodes (корни DAG) ──────────────────────────────────────
    for sn in source_nodes:
        nid = str(sn.id)
        tables: list[dict] = (sn.content or {}).get("tables", [])
        mappings = all_mappings_by_node.get(nid, [])
        if filters and mappings:
            out_tables = FilterEngine.apply_filters(tables, filters, mappings)
        else:
            out_tables = tables
        processed[nid] = out_tables
        result[nid] = {"tables": out_tables, "uses_ai": False, "from_cache": bool(not filters or not mappings)}

    # ── Шаг 3b: ContentNodes в топологическом порядке ─────────────────────────
    def _get_source_ids(cn: Any) -> list[str]:
        lineage = (cn.lineage or {}) if hasattr(cn, "lineage") else {}
        ids: list[str] = lineage.get("source_node_ids") or []
        if not ids and lineage.get("source_node_id"):
            ids = [lineage["source_node_id"]]
        return ids

    unprocessed = list(content_nodes)
    max_passes = len(content_nodes) + 1
    for _ in range(max_passes):
        if not unprocessed:
            break
        still_waiting: list[Any] = []
        for cn in unprocessed:
            nid = str(cn.id)
            source_ids = _get_source_ids(cn)

            # Ждём пока все upstream-ноды не будут обработаны
            if source_ids and not all(sid in processed for sid in source_ids):
                still_waiting.append(cn)
                continue

            # Определяем наличие AI-кода
            lineage = (cn.lineage or {}) if hasattr(cn, "lineage") else {}
            history: list[dict] = lineage.get("transformation_history", [])
            last_code: str = history[-1].get("code_snippet", "") if history else ""
            uses_ai: bool = any(_code_uses_ai(step.get("code_snippet")) for step in history)

            tables = (cn.content or {}).get("tables", [])
            mappings = all_mappings_by_node.get(nid, [])

            if last_code and not uses_ai and source_ids:
                # Пересчёт: собираем отфильтрованные DataFrame-ы из upstream
                input_data: dict[str, Any] = {}
                for sid in source_ids:
                    for tbl in processed.get(sid, []):
                        try:
                            df = python_executor.table_dict_to_dataframe(tbl)
                            input_data[tbl["name"]] = df
                        except Exception as e:
                            logger.warning("Failed to convert table '%s' for filter recompute: %s", tbl.get("name"), e)

                if input_data:
                    try:
                        exec_result = await python_executor.execute_transformation(
                            code=last_code,
                            input_data=input_data,
                            user_id=user_id,
                        )
                        if exec_result.success:
                            new_tables = [
                                python_executor.dataframe_to_table_dict(df, var)
                                for var, df in exec_result.result_dfs.items()
                            ]
                            processed[nid] = new_tables
                            result[nid] = {"tables": new_tables, "uses_ai": False, "from_cache": False}
                        else:
                            logger.warning("Filter recompute failed for %s: %s", nid, exec_result.error)
                            # Fallback: row-level filter
                            out_tables = FilterEngine.apply_filters(tables, filters, mappings) if filters and mappings else tables
                            processed[nid] = out_tables
                            result[nid] = {"tables": out_tables, "uses_ai": False, "from_cache": True}
                    except Exception as e:
                        logger.warning("Exception during filter recompute for %s: %s", nid, e)
                        processed[nid] = tables
                        result[nid] = {"tables": tables, "uses_ai": False, "from_cache": True}
                else:
                    # Нет входных данных — row-level filter
                    out_tables = FilterEngine.apply_filters(tables, filters, mappings) if filters and mappings else tables
                    processed[nid] = out_tables
                    result[nid] = {"tables": out_tables, "uses_ai": False, "from_cache": True}
            else:
                # uses_ai=True или нет кода → применяем row-level filter к кэшу
                out_tables = FilterEngine.apply_filters(tables, filters, mappings) if filters and mappings else tables
                processed[nid] = out_tables
                result[nid] = {"tables": out_tables, "uses_ai": uses_ai, "from_cache": True}

        unprocessed = still_waiting

    # Оставшиеся необработанные (циклические зависимости или нет lineage) — row-level filter
    for cn in unprocessed:
        nid = str(cn.id)
        tables = (cn.content or {}).get("tables", [])
        mappings = all_mappings_by_node.get(nid, [])
        out_tables = FilterEngine.apply_filters(tables, filters, mappings) if filters and mappings else tables
        result[nid] = {"tables": out_tables, "uses_ai": False, "from_cache": True}

    return result


@board_filter_router.post("/compute-filtered")
async def compute_filtered_board(
    board_id: UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Пересчитать всю pandas-цепочку с учётом активных фильтров.

    НЕ сохраняет результаты в БД — только для отображения на доске.
    ContentNode с ai_resolve_batch используют кэшированные данные.

    Request body: { "filters": FilterExpression | null, "initiator_content_node_ids": [str] | null }
    "nodes" всегда содержит отфильтрованные данные (для карточек ContentNode).
    "initiator_full_data" — только для node_id из initiator_content_node_ids полные данные,
    чтобы виджет-инициатор мог показывать highlight (full vs filtered).

    Response: { "nodes": { [nodeId]: { tables, uses_ai, from_cache } }, "initiator_full_data"?: { [nodeId]: { tables, ... } } }
    """
    raw_filters = body.get("filters")
    initiator_ids: list[str] = body.get("initiator_content_node_ids") or []

    logger.info(
        "compute-filtered board=%s raw_filters=%s initiator_ids=%s",
        board_id,
        type(raw_filters).__name__ if raw_filters else None,
        len(initiator_ids),
    )

    try:
        nodes_data = await _compute_filtered_pipeline(
            db=db,
            board_id=board_id,
            filters=raw_filters,
            user_id=str(current_user.id),
        )

        initiator_full_data: dict[str, dict[str, Any]] = {}
        if initiator_ids:
            full_data = await _compute_filtered_pipeline(
                db=db,
                board_id=board_id,
                filters=None,
                user_id=str(current_user.id),
            )
            for nid in initiator_ids:
                if nid in full_data:
                    initiator_full_data[nid] = full_data[nid]

        logger.info(
            "compute-filtered board=%s result_nodes=%d initiator_full=%d",
            board_id,
            len(nodes_data),
            len(initiator_full_data),
        )
        return {"nodes": nodes_data, "initiator_full_data": initiator_full_data}
    except Exception as e:
        logger.error("compute-filtered failed for board %s: %s", board_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Filter recompute failed: {str(e)}",
        )


# ═══════════════════════════════════════════════════════════════════════
#  Dashboard Filters
# ═══════════════════════════════════════════════════════════════════════

dashboard_filter_router = APIRouter(
    prefix="/api/v1/dashboards/{dashboard_id}/filters",
    tags=["filters"],
)


@dashboard_filter_router.get("", response_model=ActiveFiltersResponse)
async def get_dashboard_filters(
    dashboard_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    key = _filter_key("dashboard", str(dashboard_id), str(current_user.id))
    data = _active_filters_store.get(key, {})
    return ActiveFiltersResponse(
        filters=data.get("filters"),
        preset_id=data.get("preset_id"),
        updated_at=data.get("updated_at"),
    )


@dashboard_filter_router.put("", response_model=ActiveFiltersResponse)
async def set_dashboard_filters(
    dashboard_id: UUID,
    body: ActiveFiltersUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from datetime import datetime

    key = _filter_key("dashboard", str(dashboard_id), str(current_user.id))
    filters_dict = None
    if body.filters is not None:
        filters_dict = body.filters.model_dump() if hasattr(body.filters, "model_dump") else body.filters
    _active_filters_store[key] = {
        "filters": filters_dict,
        "preset_id": None,
        "updated_at": datetime.utcnow(),
    }
    return ActiveFiltersResponse(**_active_filters_store[key])


@dashboard_filter_router.post("/clear", response_model=ActiveFiltersResponse)
async def clear_dashboard_filters(
    dashboard_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    key = _filter_key("dashboard", str(dashboard_id), str(current_user.id))
    _active_filters_store.pop(key, None)
    return ActiveFiltersResponse(filters=None, preset_id=None, updated_at=None)


@dashboard_filter_router.post("/compute-filtered")
async def compute_filtered_dashboard(
    dashboard_id: UUID,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Пересчитать pipeline досок для виджетов дашборда с учётом фильтров.

    Вместо row-level фильтрации на агрегированных таблицах (что обнуляет данные),
    находим board_id каждого ContentNode и запускаем _compute_filtered_pipeline доски.
    Это корректно пересчитывает трансформации на отфильтрованных исходных данных.

    Request body: { "filters": FilterExpression | null, "initiator_content_node_ids": [str] | null }
    Response: { "nodes": { [contentNodeId]: { tables, uses_ai, from_cache } } }
    """
    from app.services.content_node_service import ContentNodeService
    from app.services.dashboard_service import DashboardService
    from app.models.project_widget import ProjectWidget

    raw_filters = body.get("filters")
    initiator_ids: list[str] = body.get("initiator_content_node_ids") or []
    logger.info("compute-filtered dashboard=%s raw_filters=%s initiator_ids=%d", dashboard_id, type(raw_filters).__name__ if raw_filters else None, len(initiator_ids))

    if not raw_filters:
        return {"nodes": {}}

    try:
        # 1. Загрузить дашборд с items
        dashboard = await DashboardService.get_dashboard(db, dashboard_id, current_user.id)
        if not dashboard:
            raise HTTPException(status_code=404, detail="Dashboard not found")

        # 2. Собрать content node IDs из widget items → ProjectWidget
        content_node_ids: set[UUID] = set()
        widget_items = [it for it in dashboard.items if it.item_type == "widget" and it.source_id]
        if not widget_items:
            return {"nodes": {}}

        pw_ids = [it.source_id for it in widget_items]
        from sqlalchemy import select
        pw_rows = (await db.execute(select(ProjectWidget).where(ProjectWidget.id.in_(pw_ids)))).scalars().all()
        for pw in pw_rows:
            cn_id = pw.source_content_node_id or (pw.config or {}).get("sourceContentNodeId")
            if cn_id:
                content_node_ids.add(UUID(str(cn_id)))

        if not content_node_ids:
            return {"nodes": {}}

        # 3. Группируем content nodes по board_id
        board_ids_for_cn: dict[UUID, UUID] = {}
        for cn_id in content_node_ids:
            cn = await ContentNodeService.get_content_node(db, cn_id)
            if cn and cn.board_id:
                board_ids_for_cn[cn_id] = cn.board_id

        # 4. Запускаем pipeline для каждой уникальной доски (с фильтрами)
        pipeline_results: dict[str, dict] = {}
        unique_boards = set(board_ids_for_cn.values())
        for bid in unique_boards:
            logger.info("compute-filtered dashboard=%s running board pipeline for board=%s", dashboard_id, bid)
            board_result = await _compute_filtered_pipeline(
                db=db,
                board_id=bid,
                filters=raw_filters,
                user_id=str(current_user.id),
            )
            pipeline_results.update(board_result)

        # 5. Извлекаем результаты только для нужных content nodes
        result: dict[str, dict] = {}
        for cn_id in content_node_ids:
            nid = str(cn_id)
            if nid in pipeline_results:
                result[nid] = pipeline_results[nid]

        # 6. Для виджетов-инициаторов — полные данные только в initiator_full_data (result остаётся отфильтрованным)
        initiator_full_data: dict[str, dict[str, Any]] = {}
        if initiator_ids:
            boards_with_initiators = set()
            for nid in initiator_ids:
                try:
                    boards_with_initiators.add(board_ids_for_cn[UUID(nid)])
                except (KeyError, ValueError):
                    pass
            for bid in boards_with_initiators:
                full_result = await _compute_filtered_pipeline(
                    db=db,
                    board_id=bid,
                    filters=None,
                    user_id=str(current_user.id),
                )
                for nid in initiator_ids:
                    if nid in full_result:
                        initiator_full_data[nid] = full_result[nid]

        logger.info("compute-filtered dashboard=%s result_nodes=%d initiator_full=%d", dashboard_id, len(result), len(initiator_full_data))
        return {"nodes": result, "initiator_full_data": initiator_full_data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("compute-filtered failed for dashboard %s: %s", dashboard_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Dashboard filter recompute failed: {str(e)}",
        )


@dashboard_filter_router.post("/apply-preset/{preset_id}", response_model=ActiveFiltersResponse)
async def apply_dashboard_preset(
    dashboard_id: UUID,
    preset_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from datetime import datetime

    preset = await FilterPresetService.get_preset(db, preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")
    key = _filter_key("dashboard", str(dashboard_id), str(current_user.id))
    _active_filters_store[key] = {
        "filters": preset.filters,
        "preset_id": str(preset.id),
        "updated_at": datetime.utcnow(),
    }
    return ActiveFiltersResponse(**_active_filters_store[key])


# ═══════════════════════════════════════════════════════════════════════
#  Filter Presets CRUD (project-scoped)
# ═══════════════════════════════════════════════════════════════════════

preset_router = APIRouter(
    prefix="/api/v1/projects/{project_id}/filter-presets",
    tags=["filter-presets"],
)


@preset_router.get("", response_model=list[FilterPresetResponse])
async def list_presets(
    project_id: UUID,
    scope: str | None = None,
    target_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await FilterPresetService.list_presets(db, project_id, scope, target_id)


@preset_router.post("", response_model=FilterPresetResponse, status_code=status.HTTP_201_CREATED)
async def create_preset(
    project_id: UUID,
    data: FilterPresetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    preset = await FilterPresetService.create_preset(db, project_id, current_user.id, data)  # type: ignore[arg-type]
    await db.commit()
    await db.refresh(preset)
    return preset


@preset_router.get("/{preset_id}", response_model=FilterPresetResponse)
async def get_preset(
    project_id: UUID,
    preset_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    preset = await FilterPresetService.get_preset(db, preset_id)
    if not preset or preset.project_id != project_id:
        raise HTTPException(status_code=404, detail="Preset not found")
    return preset


@preset_router.put("/{preset_id}", response_model=FilterPresetResponse)
async def update_preset(
    project_id: UUID,
    preset_id: UUID,
    data: FilterPresetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    preset = await FilterPresetService.update_preset(db, preset_id, data)
    if not preset or preset.project_id != project_id:
        raise HTTPException(status_code=404, detail="Preset not found")
    await db.commit()
    await db.refresh(preset)
    return preset


@preset_router.delete("/{preset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_preset(
    project_id: UUID,
    preset_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = await FilterPresetService.delete_preset(db, preset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Preset not found")
    await db.commit()
