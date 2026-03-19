"""
Research Chat API — чат исследования для ResearchSourceDialog.

POST /api/v1/research/chat — отправить сообщение, получить narrative + tables + sources.
См. docs/AI_RESEARCH_SOURCE_IMPLEMENTATION_PLAN.md
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.middleware.auth import get_current_user
from app.models import User
from app.schemas.research import (
    ResearchChatRequest,
    ResearchChatResponse,
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

        return ResearchChatResponse(
            narrative=result.narrative or "",
            tables=result.tables or [],
            sources=sources_out,
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
