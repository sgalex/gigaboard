from __future__ import annotations

import asyncio
from uuid import UUID

from app.core.database import async_session_maker
from app.routes.filters import _compute_filtered_pipeline, _build_dim_known_values_for_board
from app.services.filter_state_service import FilterStateService


BOARD_ID = "fd40a485-1015-42c0-a7d9-43d9cfc6ff67"
USER_ID = "e5dc48c5-c575-48ee-b423-9b0c38881744"
FILTER = {
    "type": "condition",
    "dim": "brand",
    "op": "contains",
    "value": "Phillips",
}


async def main() -> None:
    async with async_session_maker() as db:
        known_values = await _build_dim_known_values_for_board(db, UUID(BOARD_ID))
        saved = FilterStateService.add_filter_json_object(
            scope="board",
            target_id=BOARD_ID,
            user_id=USER_ID,
            filter_json=FILTER,
            dim_known_values=known_values,
        )
        print("saved_filter:", saved.get("filters"))

        active = FilterStateService.get_active_filters(
            scope="board",
            target_id=BOARD_ID,
            user_id=USER_ID,
        )
        print("active_filter:", active.get("filters"))

        nodes = await _compute_filtered_pipeline(
            db=db,
            board_id=UUID(BOARD_ID),
            filters=active.get("filters"),
            user_id=USER_ID,
        )

    print("nodes_count:", len(nodes))

    found = False
    total_rows = 0
    for node_id, entry in nodes.items():
        for table in entry.get("tables") or []:
            if str(table.get("name", "")).lower() != "top_products":
                continue
            rows = table.get("rows") or []
            found = True
            total_rows += len(rows)
            print(f"top_products node={node_id} rows={len(rows)}")
            for row in rows[:20]:
                print(
                    " -",
                    row.get("brand"),
                    "|",
                    row.get("title"),
                    "| sales=",
                    row.get("salesAmount"),
                )

    if not found:
        print("top_products table not found in filtered output")
    else:
        print("top_products total filtered rows:", total_rows)


if __name__ == "__main__":
    asyncio.run(main())

