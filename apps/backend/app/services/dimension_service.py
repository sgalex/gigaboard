"""Dimension service — CRUD for Dimensions and DimensionColumnMappings.

See docs/CROSS_FILTER_SYSTEM.md
"""
from __future__ import annotations

import logging
from difflib import SequenceMatcher
from typing import Any
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.dimension import Dimension
from app.models.dimension_column_mapping import DimensionColumnMapping
from app.schemas.cross_filter import (
    DimensionCreate,
    DimensionUpdate,
    DimensionColumnMappingCreate,
)

logger = logging.getLogger(__name__)


class DimensionService:
    """CRUD operations for Dimensions and their column mappings."""

    # ------------------------------------------------------------------ #
    #  Dimensions CRUD                                                    #
    # ------------------------------------------------------------------ #

    @staticmethod
    async def create_dimension(
        db: AsyncSession,
        project_id: UUID,
        data: DimensionCreate,
    ) -> Dimension:
        dim = Dimension(
            project_id=project_id,
            name=data.name,
            display_name=data.display_name,
            dim_type=data.dim_type.value,
            description=data.description,
            known_values=data.known_values,
        )
        db.add(dim)
        await db.flush()
        logger.info("Created Dimension %s (%s) in project %s", dim.name, dim.id, project_id)
        return dim

    @staticmethod
    async def list_dimensions(
        db: AsyncSession,
        project_id: UUID,
    ) -> list[Dimension]:
        stmt = (
            select(Dimension)
            .where(Dimension.project_id == project_id)
            .options(selectinload(Dimension.column_mappings))
            .order_by(Dimension.name)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_dimension(
        db: AsyncSession,
        dim_id: UUID,
    ) -> Dimension | None:
        stmt = (
            select(Dimension)
            .where(Dimension.id == dim_id)
            .options(selectinload(Dimension.column_mappings))
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def update_dimension(
        db: AsyncSession,
        dim_id: UUID,
        data: DimensionUpdate,
    ) -> Dimension | None:
        dim = await DimensionService.get_dimension(db, dim_id)
        if not dim:
            return None
        update_data = data.model_dump(exclude_unset=True)
        if "dim_type" in update_data and update_data["dim_type"] is not None:
            update_data["dim_type"] = update_data["dim_type"].value if hasattr(update_data["dim_type"], "value") else update_data["dim_type"]
        for key, value in update_data.items():
            setattr(dim, key, value)
        await db.flush()
        return dim

    @staticmethod
    async def delete_dimension(
        db: AsyncSession,
        dim_id: UUID,
    ) -> bool:
        dim = await DimensionService.get_dimension(db, dim_id)
        if not dim:
            return False
        await db.delete(dim)
        await db.flush()
        return True

    # ------------------------------------------------------------------ #
    #  Column Mappings CRUD                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    async def create_mapping(
        db: AsyncSession,
        data: DimensionColumnMappingCreate,
    ) -> DimensionColumnMapping:
        mapping = DimensionColumnMapping(
            dimension_id=data.dimension_id,
            node_id=data.node_id,
            table_name=data.table_name,
            column_name=data.column_name,
            mapping_source=data.mapping_source.value,
            confidence=data.confidence,
        )
        db.add(mapping)
        await db.flush()
        return mapping

    @staticmethod
    async def get_all_mappings_for_board(
        db: AsyncSession,
        board_id: UUID,
    ) -> dict[str, list[dict[str, Any]]]:
        """Return {node_id_str: [mappings]} for ALL nodes that belong to the board.

        Covers both ContentNodes and SourceNodes (SourceNode subclasses ContentNode,
        so a single join through the content_nodes table finds both).
        """
        from app.models.content_node import ContentNode as ContentNodeModel

        stmt = (
            select(DimensionColumnMapping, Dimension.name.label("dim_name"))
            .join(Dimension, DimensionColumnMapping.dimension_id == Dimension.id)
            .join(ContentNodeModel, ContentNodeModel.id == DimensionColumnMapping.node_id)
            .where(ContentNodeModel.board_id == board_id)
        )
        result = await db.execute(stmt)
        rows = result.all()

        out: dict[str, list[dict[str, Any]]] = {}
        for mapping, dim_name in rows:
            nid = str(mapping.node_id)
            out.setdefault(nid, []).append({
                "id": str(mapping.id),
                "dimension_id": str(mapping.dimension_id),
                "node_id": nid,
                "table_name": mapping.table_name,
                "column_name": mapping.column_name,
                "mapping_source": mapping.mapping_source,
                "confidence": mapping.confidence,
                "dim_name": dim_name,
            })
        return out

    @staticmethod
    async def get_mappings_for_node(
        db: AsyncSession,
        node_id: UUID,
    ) -> list[dict[str, Any]]:
        """Return mappings for a node, enriched with dim_name from Dimension."""
        stmt = (
            select(DimensionColumnMapping, Dimension.name.label("dim_name"))
            .join(Dimension, DimensionColumnMapping.dimension_id == Dimension.id)
            .where(DimensionColumnMapping.node_id == node_id)
        )
        result = await db.execute(stmt)
        rows = result.all()
        out: list[dict[str, Any]] = []
        for mapping, dim_name in rows:
            out.append({
                "id": str(mapping.id),
                "dimension_id": str(mapping.dimension_id),
                "node_id": str(mapping.node_id),
                "table_name": mapping.table_name,
                "column_name": mapping.column_name,
                "mapping_source": mapping.mapping_source,
                "confidence": mapping.confidence,
                "dim_name": dim_name,
            })
        return out

    @staticmethod
    async def get_mappings_for_dimension(
        db: AsyncSession,
        dimension_id: UUID,
    ) -> list[DimensionColumnMapping]:
        stmt = (
            select(DimensionColumnMapping)
            .where(DimensionColumnMapping.dimension_id == dimension_id)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def delete_mapping(
        db: AsyncSession,
        mapping_id: UUID,
    ) -> bool:
        stmt = select(DimensionColumnMapping).where(DimensionColumnMapping.id == mapping_id)
        result = await db.execute(stmt)
        mapping = result.scalar_one_or_none()
        if not mapping:
            return False
        await db.delete(mapping)
        await db.flush()
        return True

    @staticmethod
    async def get_dimension_values(
        db: AsyncSession,
        dim_id: UUID,
        node_ids: list[UUID] | None = None,
    ) -> list[Any]:
        """Aggregate unique values for a dimension across all mapped nodes.

        This reads ContentNode.content → tables → column and collects distinct values.
        For performance we defer to the route handler that has data access.
        Here we return mappings so the handler can extract values from content.
        """
        mappings = await DimensionService.get_mappings_for_dimension(db, dim_id)
        return mappings  # caller will extract values from content

    # ------------------------------------------------------------------ #
    #  Auto-detection on data load                                        #
    # ------------------------------------------------------------------ #

    # Type → dimension type mapping
    _COL_TYPE_TO_DIM_TYPE: dict[str, str] = {
        "string": "string",
        "text": "string",
        "number": "number",
        "integer": "number",
        "float": "number",
        "date": "date",
        "datetime": "date",
        "boolean": "boolean",
        "bool": "boolean",
    }

    # Max unique-value thresholds by column type.
    # These are ABSOLUTE upper-bounds used when row count is unknown (0).
    # For larger tables the CARDINALITY RATIO check takes over (see below).
    # date/datetime use a very high threshold — dates have many unique values
    # by design and are always useful as time dimensions.
    _MAX_UNIQUE: dict[str, int] = {
        "string": 100,
        "text": 100,
        "date": 10_000,
        "datetime": 10_000,
        "boolean": 3,
        "bool": 3,
    }
    _MAX_UNIQUE_DEFAULT = 30  # for number / integer / float

    # For string/text columns when row count is known: allow up to this fraction
    # of unique values relative to total rows before treating a column as free-text.
    # Brand with 4 000 uniques out of 500 000 rows = 0.8 % → valid dimension.
    # Order-ID with 500 000 uniques out of 500 000 rows = 100 % → skip.
    _MAX_CARDINALITY_RATIO: float = 0.30  # 30 %

    # Keywords in column names that imply a date/time dimension
    # even if the extractor reported the type as "text" or "string".
    _DATE_NAME_KEYWORDS: tuple[str, ...] = (
        "date", "time", "datetime", "timestamp", "created_at", "updated_at",
        "year", "month", "quarter", "week", "day", "period", "дата",
    )

    # Column name words that indicate an AGGREGATED METRIC (measure), not a dimension.
    # Numeric columns whose snake_case words intersect with this set are skipped
    # to avoid polluting the dimension list with values like "sales_count",
    # "total_revenue", etc.  Word-based matching (split by "_") avoids false
    # positives like "count" matching "country".
    _METRIC_KEYWORDS: frozenset[str] = frozenset({
        "count", "amount", "sum", "total", "avg", "average",
        "price", "revenue", "qty", "quantity", "cost", "profit",
        "loss", "margin", "rate", "ratio", "score", "weight",
        "value", "volume", "percent", "pct", "index", "sales",
    })

    @staticmethod
    async def auto_detect_and_upsert(
        db: AsyncSession,
        project_id: UUID,
        node_id: UUID,
        tables: list[dict[str, Any]],
        *,
        min_confidence: float = 0.4,
    ) -> list[dict[str, Any]]:
        """Detect dimensions from *tables* and create/update Dimension + Mapping rows.

        Called automatically when a SourceNode or ContentNode gets new table data.

        Algorithm per column:
        1. Compute unique-value count; skip if above type-specific threshold.
        2. Map column type → dim_type.
        3. Fuzzy-match column name against existing project dimensions (≥0.6).
           - Match found  → reuse existing Dimension (update known_values).
           - No match      → create a new Dimension.
        4. Upsert DimensionColumnMapping for (dimension, node, table, column).

        Returns list of dicts describing what was created/updated.
        """
        logger.info(
            f"📐 auto_detect_and_upsert: project={project_id}, node={node_id}, "
            f"tables_count={len(tables)}, min_confidence={min_confidence}"
        )

        if not tables:
            logger.info("📐 auto_detect_and_upsert: tables list is empty, returning []")
            return []

        # ── Load existing dimensions ──
        existing_q = await db.execute(
            select(Dimension).where(Dimension.project_id == project_id)
        )
        existing_dims: list[Dimension] = list(existing_q.scalars().all())
        dim_name_map: dict[str, Dimension] = {d.name.lower(): d for d in existing_dims}
        logger.info(f"📐 Existing dimensions in project: {list(dim_name_map.keys())}")

        results: list[dict[str, Any]] = []

        for table in tables:
            table_name = table.get("name", "")
            columns = table.get("columns", [])
            rows = table.get("rows", [])
            logger.info(
                f"📐 Table '{table_name}': {len(columns)} columns, {len(rows)} rows"
            )

            for col in columns:
                col_name: str = col.get("name", "")
                col_type: str = col.get("type", "string")
                if not col_name:
                    continue

                # ── Name-based type reclassification ──
                # CSV extractor sometimes assigns "text" to ISO-date strings.
                # If the column name looks like a date field, promote to "date".
                col_name_lower = col_name.lower()
                original_type = col_type
                if col_type in ("string", "text") and any(
                    kw in col_name_lower
                    for kw in DimensionService._DATE_NAME_KEYWORDS
                ):
                    col_type = "date"
                    logger.info(
                        f"📐   Column '{col_name}': type reclassified "
                        f"'{original_type}' → 'date' (name heuristic)"
                    )

                # ── Unique-value analysis ──
                values = [row.get(col_name) for row in rows if row.get(col_name) is not None]
                unique_strs = list(set(str(v) for v in values))
                unique_count = len(unique_strs)
                if unique_count == 0:
                    logger.info(f"📐   Column '{col_name}': skipped (0 unique values out of {len(rows)} rows)")
                    continue

                max_unique = DimensionService._MAX_UNIQUE.get(
                    col_type, DimensionService._MAX_UNIQUE_DEFAULT
                )

                # For string/text: if row count is known, use cardinality ratio
                # instead of the fixed absolute cap — this lets high-cardinality
                # but genuinely categorical columns (brand, city, category…) through.
                total_rows = len(rows)
                if unique_count > max_unique:
                    if (
                        col_type in ("string", "text")
                        and total_rows > 0
                        and (unique_count / total_rows) <= DimensionService._MAX_CARDINALITY_RATIO
                    ):
                        logger.info(
                            f"📐   Column '{col_name}' (type={col_type}): absolute cap "
                            f"exceeded ({unique_count} > {max_unique}) but cardinality "
                            f"{unique_count/total_rows:.1%} ≤ {DimensionService._MAX_CARDINALITY_RATIO:.0%} "
                            f"→ proceeding as categorical dimension"
                        )
                    else:
                        logger.info(
                            f"📐   Column '{col_name}' (type={col_type}): skipped "
                            f"(unique={unique_count} > max={max_unique}"
                            + (
                                f", cardinality={unique_count/total_rows:.1%} > {DimensionService._MAX_CARDINALITY_RATIO:.0%})"
                                if total_rows > 0 else ")"
                            )
                        )
                        continue

                dim_type = DimensionService._COL_TYPE_TO_DIM_TYPE.get(col_type, "string")

                # ── Skip numeric metrics ──
                # Numeric columns whose name contains aggregation-related words
                # (count, sum, amount, etc.) are measures, not dimensions.
                # This prevents polluting the dimension list with aggregated
                # metrics from ContentNode result tables.
                if dim_type == "number":
                    col_words = set(col_name_lower.split("_"))
                    matched_keywords = col_words & DimensionService._METRIC_KEYWORDS
                    if matched_keywords:
                        logger.info(
                            f"📐   Column '{col_name}' (type={col_type}): skipped "
                            f"(numeric metric — name words: {matched_keywords})"
                        )
                        continue

                # ── Confidence score ──
                confidence = 0.5
                if unique_count <= 20:
                    confidence += 0.1
                if col_type in ("string", "boolean", "bool"):
                    confidence += 0.1
                # Date/datetime columns are always high-value time dimensions
                if col_type in ("date", "datetime"):
                    confidence += 0.2
                confidence = min(confidence, 1.0)

                if confidence < min_confidence:
                    logger.info(
                        f"📐   Column '{col_name}' (type={col_type}): skipped "
                        f"(confidence={confidence:.2f} < min={min_confidence})"
                    )
                    continue

                logger.info(
                    f"📐   Column '{col_name}' (type={col_type}): PASSED "
                    f"(unique={unique_count}, confidence={confidence:.2f}, "
                    f"sample_values={unique_strs[:5]})"
                )

                # ── Fuzzy-match against existing dims ──
                canonical_name = col_name.lower().replace(" ", "_")
                col_lower = col_name.lower().replace("_", " ")

                best_dim: Dimension | None = None
                best_ratio = 0.0
                fuzzy_details = []
                for dname_lower, dim in dim_name_map.items():
                    ratio = SequenceMatcher(
                        None, col_lower, dname_lower.replace("_", " ")
                    ).ratio()
                    fuzzy_details.append(f"{dname_lower}={ratio:.2f}")
                    if ratio > best_ratio and ratio >= 0.6:
                        best_ratio = ratio
                        best_dim = dim

                if fuzzy_details:
                    logger.info(
                        f"📐   Fuzzy match for '{col_name}': "
                        f"scores=[{', '.join(fuzzy_details)}], "
                        f"best={'%s(%.2f)' % (best_dim.name, best_ratio) if best_dim else 'none'}"
                    )
                else:
                    logger.info(f"📐   No existing dims to fuzzy-match against for '{col_name}'")

                sample_vals = unique_strs[:30]

                # ── Upsert Dimension ──
                if best_dim is not None:
                    # Update known_values (merge new samples)
                    old_kv = best_dim.known_values or {}
                    old_vals: list[str] = old_kv.get("values", [])
                    merged = list(dict.fromkeys(old_vals + sample_vals))[:200]
                    best_dim.known_values = {"values": merged}
                    dimension = best_dim
                    action = "updated"
                    logger.info(
                        f"📐   → UPDATED existing dim '{dimension.name}' (id={dimension.id}), "
                        f"merged {len(sample_vals)} new vals, total={len(merged)}"
                    )
                else:
                    # Never auto-create FLOAT dimensions without an explicit match.
                    # Float columns with no existing dim are almost always aggregated
                    # metrics (revenue, rate, etc.). Integer columns can still be
                    # useful new dimensions (year, month_number, region_id, etc.).
                    if col_type == "float":
                        logger.info(
                            f"📐   Column '{col_name}' (type={col_type}): skipped "
                            f"(numeric — no existing dim to update; won’t auto-create)"
                        )
                        continue
                    # Create new dimension
                    dimension = Dimension(
                        project_id=project_id,
                        name=canonical_name,
                        display_name=col_name.replace("_", " ").title(),
                        dim_type=dim_type,
                        known_values={"values": sample_vals},
                    )
                    db.add(dimension)
                    logger.info(
                        f"📐   → CREATING new dim '{canonical_name}' (type={dim_type}), "
                        f"display='{col_name.replace('_', ' ').title()}', calling db.flush()..."
                    )
                    await db.flush()  # get id
                    logger.info(f"📐   → Flush OK, new dim id={dimension.id}")
                    dim_name_map[canonical_name] = dimension
                    action = "created"

                # ── Upsert DimensionColumnMapping ──
                logger.info(
                    f"📐   Checking existing mapping: dim_id={dimension.id}, "
                    f"node_id={node_id}, table='{table_name}', col='{col_name}'"
                )
                mapping_q = await db.execute(
                    select(DimensionColumnMapping).where(
                        DimensionColumnMapping.dimension_id == dimension.id,
                        DimensionColumnMapping.node_id == node_id,
                        DimensionColumnMapping.table_name == table_name,
                        DimensionColumnMapping.column_name == col_name,
                    )
                )
                existing_mapping = mapping_q.scalar_one_or_none()
                if existing_mapping is None:
                    mapping = DimensionColumnMapping(
                        dimension_id=dimension.id,
                        node_id=node_id,
                        table_name=table_name,
                        column_name=col_name,
                        mapping_source="auto",
                        confidence=round(confidence, 2),
                    )
                    db.add(mapping)
                    logger.info(
                        f"📐   → CREATED new mapping: dim='{dimension.name}' ↔ col='{col_name}' "
                        f"(confidence={confidence:.2f})"
                    )
                else:
                    # Update confidence if auto-detected again
                    old_conf = existing_mapping.confidence
                    existing_mapping.confidence = max(
                        existing_mapping.confidence, round(confidence, 2)
                    )
                    logger.info(
                        f"📐   → Mapping already exists (id={existing_mapping.id}), "
                        f"confidence {old_conf} → {existing_mapping.confidence}"
                    )

                results.append({
                    "dimension": dimension.name,
                    "column": col_name,
                    "table": table_name,
                    "action": action,
                    "confidence": round(confidence, 2),
                })

        if results:
            logger.info(
                f"📐 Final flush: {len(results)} mapping(s) for node {node_id} in project {project_id}"
            )
            await db.flush()
            logger.info("📐 Flush successful")
        else:
            logger.info(
                f"📐 No dimensions detected for node {node_id} — "
                f"no columns passed cardinality/confidence filters"
            )
        logger.info(f"📐 auto_detect_and_upsert returning {len(results)} result(s): {results}")
        return results

    @staticmethod
    async def get_project_id_for_node(
        db: AsyncSession,
        board_id: UUID,
    ) -> UUID | None:
        """Resolve board_id → project_id (one query)."""
        from app.models.board import Board
        logger.info(f"📐 get_project_id_for_node: querying Board where id={board_id}")
        result = await db.execute(
            select(Board.project_id).where(Board.id == board_id)
        )
        project_id = result.scalar_one_or_none()
        logger.info(f"📐 get_project_id_for_node: board_id={board_id} → project_id={project_id}")
        return project_id

    @staticmethod
    async def cleanup_orphaned_dimensions(
        db: AsyncSession,
        project_id: UUID,
    ) -> int:
        """Delete Dimensions that have no remaining column mappings in the project.

        Called after a SourceNode or ContentNode is deleted. The DimensionColumnMapping
        rows are cascade-deleted by PostgreSQL (FK ondelete=CASCADE on node_id), so any
        Dimension exclusively mapped to the deleted node will have 0 mappings left.

        Returns the number of Dimensions deleted.
        """
        # Find all Dimension IDs in the project that still have at least one mapping
        mapped_ids_q = await db.execute(
            select(DimensionColumnMapping.dimension_id).distinct()
        )
        mapped_ids: set[UUID] = set(mapped_ids_q.scalars().all())

        # Find Dimensions in this project with no mappings
        all_dims_q = await db.execute(
            select(Dimension).where(Dimension.project_id == project_id)
        )
        all_dims: list[Dimension] = list(all_dims_q.scalars().all())

        orphaned = [d for d in all_dims if d.id not in mapped_ids]
        for dim in orphaned:
            logger.info(
                f"📐 cleanup_orphaned_dimensions: deleting orphaned Dimension "
                f"'{dim.name}' (id={dim.id}) — no mappings remain"
            )
            await db.delete(dim)

        if orphaned:
            await db.flush()
            logger.info(
                f"📐 cleanup_orphaned_dimensions: deleted {len(orphaned)} orphaned "
                f"dimension(s) in project {project_id}"
            )
        else:
            logger.info(
                f"📐 cleanup_orphaned_dimensions: no orphaned dimensions in project {project_id}"
            )

        return len(orphaned)
