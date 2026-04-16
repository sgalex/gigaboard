"""Экспорт и импорт проекта в ZIP (серверный снимок). См. docs/API.md § Projects."""
from __future__ import annotations

import io
import json
import logging
import re
import zipfile
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Board,
    CommentNode,
    ContentNode,
    Dashboard,
    DashboardItem,
    Dimension,
    DimensionColumnMapping,
    Edge,
    EdgeType,
    FilterPreset,
    Project,
    ProjectTable,
    ProjectWidget,
    SourceNode,
    UploadedFile,
    WidgetNode,
)
from app.models.base_node import BaseNode
from app.services.file_storage import get_storage
from app.services.project_access_service import ProjectAccessService

logger = logging.getLogger(__name__)

BUNDLE_FORMAT_VERSION = 1
MANIFEST_NAME = "manifest.json"
DATA_NAME = "data.json"
FILES_PREFIX = "files/"

# Превью досок/дашбордов/библиотеки: `thumbnail_url` указывает на `/api/v1/files/image/{file_id}` (см. getFileImageUrl на фронте).
_THUMBNAIL_IMAGE_FILE_RE = re.compile(
    r"/api/v1/files/image/([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
    re.IGNORECASE,
)


def _json_safe(obj: Any) -> Any:
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, EdgeType):
        return obj.value
    return obj


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        s = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(s)
        except ValueError:
            return None
    return None


def _walk_collect_file_ids(obj: Any, out: set[str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "file_id" and isinstance(v, str) and v:
                try:
                    out.add(str(UUID(v)))
                except ValueError:
                    pass
            else:
                _walk_collect_file_ids(v, out)
    elif isinstance(obj, list):
        for item in obj:
            _walk_collect_file_ids(item, out)


def _strip_missing_file_ids(obj: Any, missing: set[str]) -> None:
    if isinstance(obj, dict):
        for k, v in list(obj.items()):
            if k == "file_id" and isinstance(v, str):
                try:
                    if str(UUID(v)) in missing:
                        obj[k] = None
                except ValueError:
                    pass
            else:
                _strip_missing_file_ids(v, missing)
    elif isinstance(obj, list):
        for item in obj:
            _strip_missing_file_ids(item, missing)


def _normalize_uuid_key(s: str) -> str:
    return str(UUID(str(s)))


def _file_id_from_thumbnail_url(url: Any) -> str | None:
    """UUID файла превью из thumbnail_url или None."""
    if url is None or not isinstance(url, str):
        return None
    s = url.strip()
    if not s:
        return None
    m = _THUMBNAIL_IMAGE_FILE_RE.search(s)
    if m:
        try:
            return str(UUID(m.group(1)))
        except ValueError:
            return None
    try:
        return str(UUID(s))
    except ValueError:
        return None


def _collect_thumbnail_file_ids(payload: dict[str, Any], out: set[str]) -> None:
    """Добавляет в out идентификаторы файлов из thumbnail_url досок, дашбордов и виджетов библиотеки."""
    for board in payload.get("boards") or []:
        fid = _file_id_from_thumbnail_url(board.get("thumbnail_url"))
        if fid:
            out.add(fid)
    for d in payload.get("dashboards") or []:
        fid = _file_id_from_thumbnail_url(d.get("thumbnail_url"))
        if fid:
            out.add(fid)
    for pw in payload.get("project_widgets") or []:
        fid = _file_id_from_thumbnail_url(pw.get("thumbnail_url"))
        if fid:
            out.add(fid)


def _strip_missing_thumbnail_urls(payload: dict[str, Any], missing: set[str]) -> None:
    """Обнуляет thumbnail_url, если файл превью отсутствует в архиве."""
    if not missing:
        return
    missing_norm = set()
    for m in missing:
        try:
            missing_norm.add(str(UUID(str(m))))
        except ValueError:
            missing_norm.add(str(m))

    def _strip_row(row: dict[str, Any]) -> None:
        fid = _file_id_from_thumbnail_url(row.get("thumbnail_url"))
        if fid and fid in missing_norm:
            row["thumbnail_url"] = None

    for board in payload.get("boards") or []:
        _strip_row(board)
    for d in payload.get("dashboards") or []:
        _strip_row(d)
    for pw in payload.get("project_widgets") or []:
        _strip_row(pw)


def _remap_thumbnail_file_ids_in_payload(payload: dict[str, Any], id_map: dict[str, str]) -> None:
    """После импорта подставляет в URL новые UUID файлов (id_map: старый id → новый)."""

    def _id_map_lookup(old: str) -> str | None:
        if old in id_map:
            return id_map[old]
        try:
            k = str(UUID(old))
        except ValueError:
            return None
        return id_map.get(k)

    def _remap_one(url: Any) -> str | None:
        if not isinstance(url, str):
            return None
        s = url.strip()
        if not s:
            return None
        m = _THUMBNAIL_IMAGE_FILE_RE.search(s)
        if not m:
            return s
        old_f = m.group(1)
        new_f = _id_map_lookup(old_f)
        if not new_f:
            return s
        return s[: m.start(1)] + new_f + s[m.end(1) :]

    for board in payload.get("boards") or []:
        if board.get("thumbnail_url"):
            board["thumbnail_url"] = _remap_one(board["thumbnail_url"])
    for d in payload.get("dashboards") or []:
        if d.get("thumbnail_url"):
            d["thumbnail_url"] = _remap_one(d["thumbnail_url"])
    for pw in payload.get("project_widgets") or []:
        if pw.get("thumbnail_url"):
            pw["thumbnail_url"] = _remap_one(pw["thumbnail_url"])


def _deep_remap_uuids(obj: Any, id_map: dict[str, str]) -> Any:
    if isinstance(obj, dict):
        return {k: _deep_remap_uuids(v, id_map) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_remap_uuids(v, id_map) for v in obj]
    if isinstance(obj, str):
        try:
            u = str(UUID(obj))
        except ValueError:
            return obj
        return id_map.get(u, obj)
    return obj


def _sanitize_import_cross_refs(remapped: dict[str, Any]) -> None:
    """Обнуляет FK на узлы/доски, которых нет в снимке (часто «битые» ссылки библиотеки на удалённый виджет)."""
    board_ids: set[UUID] = set()
    for b in remapped.get("boards") or []:
        try:
            board_ids.add(UUID(str(b["id"])))
        except (ValueError, KeyError, TypeError):
            continue

    dashboard_ids: set[UUID] = set()
    for d in remapped.get("dashboards") or []:
        try:
            dashboard_ids.add(UUID(str(d["id"])))
        except (ValueError, KeyError, TypeError):
            continue

    widget_node_ids: set[UUID] = set()
    content_node_ids: set[UUID] = set()
    for n in remapped.get("nodes") or []:
        try:
            nid = UUID(str(n["id"]))
        except (ValueError, KeyError, TypeError):
            continue
        kind = n.get("node_kind")
        if kind == "widget_node":
            widget_node_ids.add(nid)
        elif kind in ("content_node", "source_node"):
            content_node_ids.add(nid)

    lib_widget_ids = set()
    for pw in remapped.get("project_widgets") or []:
        try:
            lib_widget_ids.add(UUID(str(pw["id"])))
        except (ValueError, KeyError, TypeError):
            continue

    lib_table_ids = set()
    for pt in remapped.get("project_tables") or []:
        try:
            lib_table_ids.add(UUID(str(pt["id"])))
        except (ValueError, KeyError, TypeError):
            continue

    def _uuid_or_none(v: Any) -> UUID | None:
        if v is None or v == "":
            return None
        try:
            return UUID(str(v))
        except (ValueError, TypeError):
            return None

    for pw in remapped.get("project_widgets") or []:
        sw = _uuid_or_none(pw.get("source_widget_node_id"))
        if sw is not None and sw not in widget_node_ids:
            pw["source_widget_node_id"] = None
        sc = _uuid_or_none(pw.get("source_content_node_id"))
        if sc is not None and sc not in content_node_ids:
            pw["source_content_node_id"] = None
        sb = _uuid_or_none(pw.get("source_board_id"))
        if sb is not None and sb not in board_ids:
            pw["source_board_id"] = None

    for pt in remapped.get("project_tables") or []:
        scn = _uuid_or_none(pt.get("source_content_node_id"))
        if scn is not None and scn not in content_node_ids:
            pt["source_content_node_id"] = None
        sb = _uuid_or_none(pt.get("source_board_id"))
        if sb is not None and sb not in board_ids:
            pt["source_board_id"] = None

    for it in remapped.get("dashboard_items") or []:
        sid = _uuid_or_none(it.get("source_id"))
        if sid is None:
            continue
        itype = it.get("item_type")
        if itype == "widget" and sid not in lib_widget_ids:
            it["source_id"] = None
        elif itype == "table" and sid not in lib_table_ids:
            it["source_id"] = None

    for fp in remapped.get("filter_presets") or []:
        tid = _uuid_or_none(fp.get("target_id"))
        if tid is None:
            continue
        scope = fp.get("scope") or "project"
        if scope == "board" and tid not in board_ids:
            fp["target_id"] = None
        elif scope == "dashboard" and tid not in dashboard_ids:
            fp["target_id"] = None


class ProjectBundleService:
    @staticmethod
    async def export_zip(db: AsyncSession, project_id: UUID, user_id: UUID) -> tuple[bytes, str]:
        """Возвращает (zip_bytes, project_name) для имени файла в Content-Disposition."""
        await ProjectAccessService.require_project_edit_access(db, project_id, user_id)

        stmt = (
            select(Project)
            .where(Project.id == project_id)
            .options(
                selectinload(Project.boards).selectinload(Board.nodes),
                selectinload(Project.boards).selectinload(Board.edges),
                selectinload(Project.dashboards).selectinload(Dashboard.items),
                selectinload(Project.project_widgets),
                selectinload(Project.project_tables),
                selectinload(Project.dimensions).selectinload(Dimension.column_mappings),
                selectinload(Project.filter_presets),
            )
        )
        result = await db.execute(stmt)
        project = result.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

        data: dict[str, Any] = {
            "format_version": BUNDLE_FORMAT_VERSION,
            "project": {
                "id": str(project.id),
                "name": project.name,
                "description": project.description,
                "created_at": project.created_at,
                "updated_at": project.updated_at,
            },
            "boards": [],
            "nodes": [],
            "edges": [],
            "dimensions": [],
            "dimension_column_mappings": [],
            "filter_presets": [],
            "project_widgets": [],
            "project_tables": [],
            "dashboards": [],
            "dashboard_items": [],
            "files_index": [],
        }

        for board in project.boards:
            data["boards"].append(
                {
                    "id": str(board.id),
                    "project_id": str(board.project_id),
                    "user_id": str(board.user_id),
                    "name": board.name,
                    "description": board.description,
                    "settings": board.settings,
                    "thumbnail_url": board.thumbnail_url,
                    "created_at": board.created_at,
                    "updated_at": board.updated_at,
                }
            )
            for node in board.nodes:
                data["nodes"].append(ProjectBundleService._serialize_node(node))
            for edge in board.edges:
                if edge.deleted_at is not None:
                    continue
                data["edges"].append(ProjectBundleService._serialize_edge(edge))

        for dim in project.dimensions:
            data["dimensions"].append(
                {
                    "id": str(dim.id),
                    "project_id": str(dim.project_id),
                    "name": dim.name,
                    "display_name": dim.display_name,
                    "dim_type": dim.dim_type,
                    "description": dim.description,
                    "known_values": dim.known_values,
                    "created_at": dim.created_at,
                    "updated_at": dim.updated_at,
                }
            )
            for m in dim.column_mappings:
                data["dimension_column_mappings"].append(
                    {
                        "id": str(m.id),
                        "dimension_id": str(m.dimension_id),
                        "node_id": str(m.node_id),
                        "table_name": m.table_name,
                        "column_name": m.column_name,
                        "mapping_source": m.mapping_source,
                        "confidence": m.confidence,
                        "created_at": m.created_at,
                    }
                )

        for fp in project.filter_presets:
            data["filter_presets"].append(
                {
                    "id": str(fp.id),
                    "project_id": str(fp.project_id),
                    "created_by": str(fp.created_by),
                    "name": fp.name,
                    "description": fp.description,
                    "filters": fp.filters,
                    "scope": fp.scope,
                    "target_id": str(fp.target_id) if fp.target_id else None,
                    "is_default": fp.is_default,
                    "tags": list(fp.tags or []),
                    "created_at": fp.created_at,
                    "updated_at": fp.updated_at,
                }
            )

        for pw in project.project_widgets:
            data["project_widgets"].append(
                {
                    "id": str(pw.id),
                    "project_id": str(pw.project_id),
                    "created_by": str(pw.created_by),
                    "name": pw.name,
                    "description": pw.description,
                    "html_code": pw.html_code,
                    "css_code": pw.css_code,
                    "js_code": pw.js_code,
                    "thumbnail_url": pw.thumbnail_url,
                    "source_widget_node_id": str(pw.source_widget_node_id)
                    if pw.source_widget_node_id
                    else None,
                    "source_content_node_id": str(pw.source_content_node_id)
                    if pw.source_content_node_id
                    else None,
                    "source_board_id": str(pw.source_board_id) if pw.source_board_id else None,
                    "config": pw.config,
                    "created_at": pw.created_at,
                    "updated_at": pw.updated_at,
                }
            )

        for pt in project.project_tables:
            data["project_tables"].append(
                {
                    "id": str(pt.id),
                    "project_id": str(pt.project_id),
                    "created_by": str(pt.created_by),
                    "name": pt.name,
                    "description": pt.description,
                    "columns": pt.columns,
                    "sample_data": pt.sample_data,
                    "row_count": pt.row_count,
                    "source_content_node_id": str(pt.source_content_node_id)
                    if pt.source_content_node_id
                    else None,
                    "source_board_id": str(pt.source_board_id) if pt.source_board_id else None,
                    "table_name_in_node": pt.table_name_in_node,
                    "config": pt.config,
                    "created_at": pt.created_at,
                    "updated_at": pt.updated_at,
                }
            )

        for dash in project.dashboards:
            data["dashboards"].append(
                {
                    "id": str(dash.id),
                    "project_id": str(dash.project_id),
                    "created_by": str(dash.created_by),
                    "name": dash.name,
                    "description": dash.description,
                    "status": dash.status,
                    "thumbnail_url": dash.thumbnail_url,
                    "settings": dash.settings,
                    "created_at": dash.created_at,
                    "updated_at": dash.updated_at,
                }
            )
            for item in dash.items:
                data["dashboard_items"].append(
                    {
                        "id": str(item.id),
                        "dashboard_id": str(item.dashboard_id),
                        "item_type": item.item_type,
                        "source_id": str(item.source_id) if item.source_id else None,
                        "layout": item.layout,
                        "overrides": item.overrides,
                        "content": item.content,
                        "z_index": item.z_index,
                        "created_at": item.created_at,
                        "updated_at": item.updated_at,
                    }
                )

        file_ids: set[str] = set()
        _walk_collect_file_ids(data, file_ids)
        _collect_thumbnail_file_ids(data, file_ids)

        storage = get_storage()
        files_meta: list[dict[str, Any]] = []
        file_bytes: dict[str, bytes] = {}

        for fid in sorted(file_ids):
            try:
                raw = await storage.get(fid, db=db)
                if isinstance(raw, bytes):
                    content = raw
                else:
                    from pathlib import Path

                    path = raw if isinstance(raw, Path) else Path(str(raw))
                    content = path.read_bytes()
                file_bytes[fid] = content
                r = await db.execute(select(UploadedFile).where(UploadedFile.id == UUID(fid)))
                uf = r.scalar_one_or_none()
                files_meta.append(
                    {
                        "id": fid,
                        "filename": uf.filename if uf else "file.bin",
                        "mime_type": uf.mime_type if uf else "application/octet-stream",
                        "size_bytes": len(content),
                    }
                )
            except Exception as e:
                logger.warning("Export: skip file %s: %s", fid, e)

        data["files_index"] = files_meta

        manifest = {
            "bundle": "gigaboard_project",
            "format_version": BUNDLE_FORMAT_VERSION,
            "exported_at": datetime.utcnow().isoformat() + "Z",
            "origin_project_id": str(project.id),
            "origin_project_name": project.name,
        }

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(MANIFEST_NAME, json.dumps(_json_safe(manifest), ensure_ascii=False, indent=2))
            zf.writestr(DATA_NAME, json.dumps(_json_safe(data), ensure_ascii=False, indent=2))
            for fid, content in file_bytes.items():
                zf.writestr(f"{FILES_PREFIX}{fid}", content)
        return buf.getvalue(), project.name

    @staticmethod
    def _serialize_node(node: BaseNode) -> dict[str, Any]:
        base = {
            "node_kind": "base",
            "id": str(node.id),
            "board_id": str(node.board_id),
            "node_type": node.node_type,
            "x": node.x,
            "y": node.y,
            "width": node.width,
            "height": node.height,
            "created_at": node.created_at,
            "updated_at": node.updated_at,
        }
        if isinstance(node, SourceNode):
            return {
                **base,
                "node_kind": "source_node",
                "content": node.content,
                "lineage": node.lineage,
                "node_metadata": node.node_metadata,
                "position": node.position,
                "source_type": node.source_type,
                "config": node.config,
                "created_by": str(node.created_by),
            }
        if isinstance(node, ContentNode):
            return {
                **base,
                "node_kind": "content_node",
                "content": node.content,
                "lineage": node.lineage,
                "node_metadata": node.node_metadata,
                "position": node.position,
            }
        if isinstance(node, WidgetNode):
            return {
                **base,
                "node_kind": "widget_node",
                "name": node.name,
                "description": node.description,
                "html_code": node.html_code,
                "css_code": node.css_code,
                "js_code": node.js_code,
                "config": node.config,
                "auto_refresh": node.auto_refresh,
                "refresh_interval": node.refresh_interval,
                "generated_by": node.generated_by,
                "generation_prompt": node.generation_prompt,
            }
        if isinstance(node, CommentNode):
            return {
                **base,
                "node_kind": "comment_node",
                "author_id": str(node.author_id),
                "content": node.content,
                "format_type": node.format_type,
                "color": node.color,
                "config": node.config,
                "is_resolved": node.is_resolved,
                "resolved_at": node.resolved_at,
                "resolved_by": str(node.resolved_by) if node.resolved_by else None,
            }
        return base

    @staticmethod
    def _serialize_edge(edge: Edge) -> dict[str, Any]:
        return {
            "id": str(edge.id),
            "board_id": str(edge.board_id),
            "source_node_id": str(edge.source_node_id),
            "target_node_id": str(edge.target_node_id),
            "source_node_type": edge.source_node_type,
            "target_node_type": edge.target_node_type,
            "edge_type": edge.edge_type.value if isinstance(edge.edge_type, EdgeType) else str(edge.edge_type),
            "label": edge.label,
            "parameter_mapping": edge.parameter_mapping or {},
            "transformation_code": edge.transformation_code,
            "transformation_params": edge.transformation_params or {},
            "visual_config": edge.visual_config or {},
            "created_at": edge.created_at,
            "updated_at": edge.updated_at,
            "is_valid": edge.is_valid,
            "validation_errors": edge.validation_errors,
        }

    @staticmethod
    async def import_zip(
        db: AsyncSession,
        user_id: UUID,
        zip_bytes: bytes,
        project_name: str | None = None,
    ) -> Project:
        try:
            zf_ctx = zipfile.ZipFile(io.BytesIO(zip_bytes), "r")
        except zipfile.BadZipFile as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Некорректный ZIP-архив",
            ) from e

        with zf_ctx as zf:
            try:
                manifest = json.loads(zf.read(MANIFEST_NAME).decode("utf-8"))
            except KeyError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"В архиве отсутствует {MANIFEST_NAME}",
                ) from e
            if manifest.get("bundle") != "gigaboard_project":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Неизвестный тип архива (ожидается gigaboard_project)",
                )
            fv = manifest.get("format_version")
            if fv != BUNDLE_FORMAT_VERSION:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Неподдерживаемая версия формата: {fv}",
                )
            try:
                payload = json.loads(zf.read(DATA_NAME).decode("utf-8"))
            except KeyError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"В архиве отсутствует {DATA_NAME}",
                ) from e

            zip_names = set(zf.namelist())
            referenced_files: set[str] = set()
            _walk_collect_file_ids(payload, referenced_files)
            _collect_thumbnail_file_ids(payload, referenced_files)
            present_files = {
                n[len(FILES_PREFIX) :]
                for n in zip_names
                if n.startswith(FILES_PREFIX) and len(n) > len(FILES_PREFIX)
            }
            missing_files = {f for f in referenced_files if f not in present_files}
            if missing_files:
                _strip_missing_file_ids(payload, missing_files)
                _strip_missing_thumbnail_urls(payload, missing_files)

            referenced_after: set[str] = set()
            _walk_collect_file_ids(payload, referenced_after)
            _collect_thumbnail_file_ids(payload, referenced_after)

            file_contents: dict[str, bytes] = {}
            for old_fid in referenced_after & present_files:
                try:
                    file_contents[old_fid] = zf.read(f"{FILES_PREFIX}{old_fid}")
                except KeyError:
                    continue

        id_map: dict[str, str] = {}

        def alloc(old: str) -> str:
            if old not in id_map:
                id_map[old] = str(uuid4())
            return id_map[old]

        p = payload.get("project") or {}
        old_pid = p.get("id")
        if not old_pid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="В data.json нет project.id",
            )
        alloc(str(old_pid))

        for b in payload.get("boards") or []:
            alloc(str(b["id"]))
        for n in payload.get("nodes") or []:
            alloc(str(n["id"]))
        for e in payload.get("edges") or []:
            alloc(str(e["id"]))
        for d in payload.get("dimensions") or []:
            alloc(str(d["id"]))
        for m in payload.get("dimension_column_mappings") or []:
            alloc(str(m["id"]))
        for fp in payload.get("filter_presets") or []:
            alloc(str(fp["id"]))
        for pw in payload.get("project_widgets") or []:
            alloc(str(pw["id"]))
        for pt in payload.get("project_tables") or []:
            alloc(str(pt["id"]))
        for d in payload.get("dashboards") or []:
            alloc(str(d["id"]))
        for it in payload.get("dashboard_items") or []:
            alloc(str(it["id"]))

        for fid in referenced_after & present_files:
            alloc(str(fid))

        remapped = _deep_remap_uuids(payload, id_map)
        _sanitize_import_cross_refs(remapped)
        _remap_thumbnail_file_ids_in_payload(remapped, id_map)

        rp = remapped["project"]
        new_name = project_name or f"{rp.get('name', 'Project')} (import)"
        new_description = rp.get("description")

        project = Project(
            id=UUID(id_map[str(old_pid)]),
            user_id=user_id,
            name=new_name[:200],
            description=new_description,
        )
        db.add(project)
        await db.flush()

        storage = get_storage()
        files_index = {str(x["id"]): x for x in (payload.get("files_index") or [])}

        for old_fid, content in file_contents.items():
            new_fid = id_map.get(old_fid)
            if not new_fid:
                continue
            meta = files_index.get(old_fid, {})
            fname = meta.get("filename") or "file.bin"
            mime = meta.get("mime_type") or "application/octet-stream"
            bio = io.BytesIO(content)
            await storage.save(new_fid, bio, user_id, fname, db=db, mime_type=mime)

        for b in remapped.get("boards") or []:
            board = Board(
                id=UUID(b["id"]),
                project_id=project.id,
                user_id=user_id,
                name=(b.get("name") or "Board")[:200],
                description=b.get("description"),
                settings=b.get("settings"),
                thumbnail_url=b.get("thumbnail_url"),
                created_at=_parse_dt(b.get("created_at")) or datetime.utcnow(),
                updated_at=_parse_dt(b.get("updated_at")) or datetime.utcnow(),
            )
            db.add(board)

        for n in remapped.get("nodes") or []:
            ProjectBundleService._add_node_from_payload(db, n, user_id)
        await db.flush()

        for e in remapped.get("edges") or []:
            edge = Edge(
                id=UUID(e["id"]),
                board_id=UUID(e["board_id"]),
                source_node_id=UUID(e["source_node_id"]),
                target_node_id=UUID(e["target_node_id"]),
                source_node_type=e["source_node_type"],
                target_node_type=e["target_node_type"],
                edge_type=EdgeType(e["edge_type"]),
                label=e.get("label"),
                parameter_mapping=e.get("parameter_mapping") or {},
                transformation_code=e.get("transformation_code"),
                transformation_params=e.get("transformation_params") or {},
                visual_config=e.get("visual_config") or {},
                created_at=_parse_dt(e.get("created_at")) or datetime.utcnow(),
                updated_at=_parse_dt(e.get("updated_at")) or datetime.utcnow(),
                deleted_at=None,
                is_valid=str(e.get("is_valid") or "true"),
                validation_errors=e.get("validation_errors"),
            )
            db.add(edge)

        for d in remapped.get("dimensions") or []:
            dim = Dimension(
                id=UUID(d["id"]),
                project_id=project.id,
                name=d["name"][:100],
                display_name=(d.get("display_name") or d["name"])[:200],
                dim_type=d.get("dim_type") or "string",
                description=d.get("description"),
                known_values=d.get("known_values"),
                created_at=_parse_dt(d.get("created_at")) or datetime.utcnow(),
                updated_at=_parse_dt(d.get("updated_at")) or datetime.utcnow(),
            )
            db.add(dim)

        for m in remapped.get("dimension_column_mappings") or []:
            mapping = DimensionColumnMapping(
                id=UUID(m["id"]),
                dimension_id=UUID(m["dimension_id"]),
                node_id=UUID(m["node_id"]),
                table_name=m["table_name"][:200],
                column_name=m["column_name"][:200],
                mapping_source=m.get("mapping_source") or "manual",
                confidence=float(m.get("confidence") or 1.0),
                created_at=_parse_dt(m.get("created_at")) or datetime.utcnow(),
            )
            db.add(mapping)

        for fp in remapped.get("filter_presets") or []:
            tid = fp.get("target_id")
            preset = FilterPreset(
                id=UUID(fp["id"]),
                project_id=project.id,
                created_by=user_id,
                name=fp["name"][:200],
                description=fp.get("description"),
                filters=fp.get("filters") or {},
                scope=fp.get("scope") or "project",
                target_id=UUID(tid) if tid else None,
                is_default=bool(fp.get("is_default")),
                tags=list(fp.get("tags") or []),
                created_at=_parse_dt(fp.get("created_at")) or datetime.utcnow(),
                updated_at=_parse_dt(fp.get("updated_at")) or datetime.utcnow(),
            )
            db.add(preset)

        for pw in remapped.get("project_widgets") or []:
            sw = pw.get("source_widget_node_id")
            sc = pw.get("source_content_node_id")
            sb = pw.get("source_board_id")
            w = ProjectWidget(
                id=UUID(pw["id"]),
                project_id=project.id,
                created_by=user_id,
                name=(pw.get("name") or "Widget")[:200],
                description=pw.get("description"),
                html_code=pw.get("html_code"),
                css_code=pw.get("css_code"),
                js_code=pw.get("js_code"),
                thumbnail_url=pw.get("thumbnail_url"),
                source_widget_node_id=UUID(sw) if sw else None,
                source_content_node_id=UUID(sc) if sc else None,
                source_board_id=UUID(sb) if sb else None,
                config=pw.get("config"),
                created_at=_parse_dt(pw.get("created_at")) or datetime.utcnow(),
                updated_at=_parse_dt(pw.get("updated_at")) or datetime.utcnow(),
            )
            db.add(w)

        for pt in remapped.get("project_tables") or []:
            scn = pt.get("source_content_node_id")
            sb = pt.get("source_board_id")
            t = ProjectTable(
                id=UUID(pt["id"]),
                project_id=project.id,
                created_by=user_id,
                name=(pt.get("name") or "Table")[:200],
                description=pt.get("description"),
                columns=pt.get("columns"),
                sample_data=pt.get("sample_data"),
                row_count=int(pt.get("row_count") or 0),
                source_content_node_id=UUID(scn) if scn else None,
                source_board_id=UUID(sb) if sb else None,
                table_name_in_node=pt.get("table_name_in_node"),
                config=pt.get("config"),
                created_at=_parse_dt(pt.get("created_at")) or datetime.utcnow(),
                updated_at=_parse_dt(pt.get("updated_at")) or datetime.utcnow(),
            )
            db.add(t)

        for d in remapped.get("dashboards") or []:
            dash = Dashboard(
                id=UUID(d["id"]),
                project_id=project.id,
                created_by=user_id,
                name=(d.get("name") or "Dashboard")[:200],
                description=d.get("description"),
                status=d.get("status") or "draft",
                thumbnail_url=d.get("thumbnail_url"),
                settings=d.get("settings"),
                created_at=_parse_dt(d.get("created_at")) or datetime.utcnow(),
                updated_at=_parse_dt(d.get("updated_at")) or datetime.utcnow(),
            )
            db.add(dash)

        for it in remapped.get("dashboard_items") or []:
            sid = it.get("source_id")
            item = DashboardItem(
                id=UUID(it["id"]),
                dashboard_id=UUID(it["dashboard_id"]),
                item_type=it["item_type"],
                source_id=UUID(sid) if sid else None,
                layout=it.get("layout") or {},
                overrides=it.get("overrides"),
                content=it.get("content"),
                z_index=int(it.get("z_index") or 0),
                created_at=_parse_dt(it.get("created_at")) or datetime.utcnow(),
                updated_at=_parse_dt(it.get("updated_at")) or datetime.utcnow(),
            )
            db.add(item)

        try:
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            logger.warning("import_zip integrity error: %s", e)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Импорт: нарушение целостности данных (возможно устаревший архив). Попробуйте заново экспортировать проект.",
            ) from e

        await db.refresh(project)
        return project

    @staticmethod
    def _add_node_from_payload(db: AsyncSession, n: dict[str, Any], user_id: UUID) -> None:
        kind = n.get("node_kind") or "base"
        bid = UUID(n["board_id"])
        nid = UUID(n["id"])
        x, y = int(n.get("x") or 0), int(n.get("y") or 0)
        width = n.get("width")
        height = n.get("height")
        created_at = _parse_dt(n.get("created_at")) or datetime.utcnow()
        updated_at = _parse_dt(n.get("updated_at")) or datetime.utcnow()

        if kind == "source_node":
            node = SourceNode(
                id=nid,
                board_id=bid,
                content=n.get("content") or {"text": "", "tables": []},
                lineage=n.get("lineage") or {},
                node_metadata=n.get("node_metadata") or {},
                position=n.get("position") or {"x": 0, "y": 0},
                source_type=n["source_type"],
                config=n.get("config") or {},
                created_by=user_id,
            )
            node.x = x
            node.y = y
            node.width = width
            node.height = height
            node.created_at = created_at
            node.updated_at = updated_at
            db.add(node)
            return
        if kind == "content_node":
            node = ContentNode(
                id=nid,
                board_id=bid,
                content=n.get("content") or {"text": "", "tables": []},
                lineage=n.get("lineage") or {},
                node_metadata=n.get("node_metadata") or {},
                position=n.get("position") or {"x": 0, "y": 0},
            )
            node.x = x
            node.y = y
            node.width = width
            node.height = height
            node.created_at = created_at
            node.updated_at = updated_at
            db.add(node)
            return
        if kind == "widget_node":
            node = WidgetNode(
                id=nid,
                board_id=bid,
                name=(n.get("name") or "Widget")[:200],
                description=n.get("description") or "",
                html_code=n.get("html_code") or "",
                css_code=n.get("css_code"),
                js_code=n.get("js_code"),
                config=n.get("config"),
                auto_refresh=bool(n.get("auto_refresh", True)),
                refresh_interval=n.get("refresh_interval"),
                generated_by=n.get("generated_by"),
                generation_prompt=n.get("generation_prompt"),
            )
            node.x = x
            node.y = y
            node.width = width
            node.height = height
            node.created_at = created_at
            node.updated_at = updated_at
            db.add(node)
            return
        if kind == "comment_node":
            node = CommentNode(
                id=nid,
                board_id=bid,
                author_id=user_id,
                content=n.get("content") or "",
                format_type=n.get("format_type") or "markdown",
                color=n.get("color"),
                config=n.get("config"),
                is_resolved=bool(n.get("is_resolved")),
                resolved_at=_parse_dt(n.get("resolved_at")),
                resolved_by=None,
            )
            node.x = x
            node.y = y
            node.width = width
            node.height = height
            node.created_at = created_at
            node.updated_at = updated_at
            db.add(node)
            return

        logger.warning("import: пропуск неизвестного node_kind=%s id=%s", kind, nid)
