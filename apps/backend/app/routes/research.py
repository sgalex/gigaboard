"""
Research Chat API — чат исследования для ResearchSourceDialog.

POST /api/v1/research/chat — отправить сообщение, получить narrative + tables + sources.
POST /api/v1/research/chat-stream — NDJSON прогресс + результат.
См. docs/AI_RESEARCH_SOURCE_IMPLEMENTATION_PLAN.md
"""
import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.middleware.auth import get_current_user
from app.models import User
from app.schemas.research import (
    ResearchChatRequest,
    ResearchChatResponse,
    ResearchDiscoveredResourceRef,
    ResearchSourceRef,
)
from app.services.controllers import ResearchController

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/research", tags=["research"])


def _get_orchestrator_or_503():
    """Get Orchestrator V2 or raise 503."""
    from app.main import get_orchestrator
    orch = get_orchestrator()
    if not orch:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Orchestrator not initialized. Check backend logs.",
        )
    return orch


@router.post("/chat", response_model=ResearchChatResponse)
async def research_chat(
    request: ResearchChatRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Отправить сообщение в Research Chat (Deep Research).

    Вызывает ResearchController → Orchestrator (discovery → research
    → structurizer → analyst → reporter). Возвращает narrative, tables, sources
    для отображения в ResearchSourceDialog (превью справа).
    """
    try:
        orchestrator = _get_orchestrator_or_503()
        controller = ResearchController(orchestrator)

        chat_history = None
        if request.chat_history:
            chat_history = [
                {"role": m.role, "content": m.content}
                for m in request.chat_history
            ]

        result = await controller.process_request(
            request.message,
            context={
                "session_id": request.session_id,
                "chat_history": chat_history or [],
                "user_id": str(current_user.id),
            },
        )

        if result.status == "error":
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=result.error or "Research failed",
            )

        sources_out = [
            ResearchSourceRef(url=s.get("url", ""), title=s.get("title", s.get("url", "")))
            for s in (result.sources or [])
        ]
        discovered_out = [
            ResearchDiscoveredResourceRef(
                url=d.get("url", ""),
                resource_kind=d.get("resource_kind"),
                mime_type=d.get("mime_type"),
                parent_url=d.get("parent_url"),
                origin=d.get("origin"),
                tag=d.get("tag"),
                title=d.get("title"),
            )
            for d in (result.discovered_resources or [])
            if isinstance(d, dict) and d.get("url")
        ]

        return ResearchChatResponse(
            narrative=result.narrative or "",
            tables=result.tables or [],
            sources=sources_out,
            discovered_resources=discovered_out,
            session_id=result.session_id or "",
            execution_time_ms=result.execution_time_ms,
            plan=result.plan,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Research chat error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Research failed: {str(e)}",
        )


@router.post("/chat-stream")
async def research_chat_stream(
    request: ResearchChatRequest,
    current_user: User = Depends(get_current_user),
):
    """NDJSON: прогресс мультиагента + narrative/tables/sources (ResearchSourceDialog)."""
    queue: asyncio.Queue[dict] = asyncio.Queue()

    async def _progress_callback(progress_payload: dict) -> None:
        payload = progress_payload or {}
        if payload.get("event") == "plan_update":
            await queue.put(
                {
                    "type": "plan",
                    "steps": payload.get("steps") or [],
                    "completed_count": payload.get("completed_count") or 0,
                    "source": payload.get("source"),
                }
            )
            return
        await queue.put({"type": "progress", **payload})

    async def _run_pipeline() -> None:
        try:
            await queue.put({"type": "start"})
            orchestrator = _get_orchestrator_or_503()
            controller = ResearchController(orchestrator)

            chat_history = None
            if request.chat_history:
                chat_history = [
                    {"role": m.role, "content": m.content}
                    for m in request.chat_history
                ]

            result = await controller.process_request(
                request.message,
                context={
                    "session_id": request.session_id,
                    "chat_history": chat_history or [],
                    "user_id": str(current_user.id),
                    "_progress_callback": _progress_callback,
                    "_enable_plan_progress": True,
                },
            )

            if result.status == "error":
                await queue.put(
                    {"type": "error", "error": result.error or "Research failed"}
                )
                return

            sources_out = [
                {"url": s.get("url", ""), "title": s.get("title", s.get("url", ""))}
                for s in (result.sources or [])
            ]
            discovered_out = [
                {
                    "url": d.get("url", ""),
                    "resource_kind": d.get("resource_kind"),
                    "mime_type": d.get("mime_type"),
                    "parent_url": d.get("parent_url"),
                    "origin": d.get("origin"),
                    "tag": d.get("tag"),
                    "title": d.get("title"),
                }
                for d in (result.discovered_resources or [])
                if isinstance(d, dict) and d.get("url")
            ]
            await queue.put(
                {
                    "type": "result",
                    "result": {
                        "narrative": result.narrative or "",
                        "tables": result.tables or [],
                        "sources": sources_out,
                        "discovered_resources": discovered_out,
                        "session_id": result.session_id or "",
                        "execution_time_ms": result.execution_time_ms,
                        "plan": result.plan,
                    },
                }
            )
        except HTTPException as e:
            await queue.put({"type": "error", "error": str(e.detail)})
        except Exception as e:
            logger.exception(f"Research chat stream error: {e}")
            await queue.put({"type": "error", "error": str(e)})
        finally:
            await queue.put({"type": "done"})

    async def _event_stream():
        task = asyncio.create_task(_run_pipeline())
        try:
            while True:
                item = await queue.get()
                yield json.dumps(item, ensure_ascii=False, default=str) + "\n"
                if item.get("type") == "done":
                    break
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(_event_stream(), media_type="application/x-ndjson")
