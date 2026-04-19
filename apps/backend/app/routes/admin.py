"""
Роуты для администратора: модели LLM (llm_config), системные настройки (default + привязки агентов),
тест LLM, Playground мультиагента. Доступ только при role=admin.
См. docs/ADMIN_AND_SYSTEM_LLM.md, docs/LLM_CONFIGURATION_CONCEPT.md.
"""
import asyncio
import httpx
import json
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import get_db
from app.middleware import get_current_admin_user
from app.models import User, SystemLLMSettings, LLMConfig, AgentLLMOverride
from app.schemas import (
    LLMProvider,
    GigaChatModelInfo,
    LLMConfigResponse,
    LLMConfigCreate,
    LLMConfigUpdate,
    SystemLLMSettingsResponse,
    SystemLLMSettingsUpdate,
    AgentLLMOverrideItem,
    AgentLLMOverridesSet,
    SystemLLMPlaygroundRunRequest,
    UserAISettingsTestResponse,
    UserSearchResult,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

GIGACHAT_MODELS: list[dict[str, str]] = [
    {"id": "GigaChat", "name": "GigaChat", "description": "Базовая модель"},
    {"id": "GigaChat-Pro", "name": "GigaChat-Pro", "description": "Продвинутая модель"},
    {"id": "GigaChat-Max", "name": "GigaChat-Max", "description": "Максимальные возможности"},
    {"id": "GigaChat-Mini", "name": "GigaChat-Mini", "description": "Облегчённая модель"},
]

AGENT_KEYS = [
    "planner", "discovery", "research", "structurizer", "analyst",
    "transform_codex", "widget_codex", "reporter", "validator",
    # Служебные ключи привязки LLM (не шаги плана), см. LLM_CONFIGURATION_CONCEPT.md
    "context_graph_compression",
]


@router.get(
    "/users",
    response_model=list[UserSearchResult],
    status_code=status.HTTP_200_OK,
)
async def list_users_for_admin(
    q: str = Query("", max_length=200, description="Поиск по username/email"),
    limit: int = Query(100, ge=1, le=500, description="Максимум записей"),
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> list[UserSearchResult]:
    """Список пользователей системы для admin (поиск + ограничение)."""
    term = (q or "").strip()
    stmt = select(User).where(User.deleted_at.is_(None))
    if term:
        pat = f"%{term}%"
        stmt = stmt.where(or_(User.username.ilike(pat), User.email.ilike(pat)))
    stmt = stmt.order_by(User.username.asc()).limit(limit)
    result = await db.execute(stmt)
    users = result.scalars().all()
    return [
        UserSearchResult(id=u.id, username=u.username, email=u.email)
        for u in users
    ]


def _llm_config_to_response(c: LLMConfig) -> LLMConfigResponse:
    return LLMConfigResponse(
        id=c.id,
        name=c.name,
        provider=LLMProvider(c.provider),
        sort_order=c.sort_order or 0,
        gigachat_model=c.gigachat_model,
        gigachat_scope=c.gigachat_scope,
        has_gigachat_api_key=bool(c.gigachat_api_key_encrypted),
        external_base_url=c.external_base_url,
        external_default_model=c.external_default_model,
        external_timeout_seconds=c.external_timeout_seconds,
        has_external_api_key=bool(c.external_api_key_encrypted),
        temperature=c.temperature,
        max_tokens=c.max_tokens,
    )


async def _get_or_create_system_llm_settings(db: AsyncSession) -> SystemLLMSettings:
    result = await db.execute(select(SystemLLMSettings).limit(1))
    row = result.scalar_one_or_none()
    if row is not None:
        return row
    # Создать запись; default_llm_config_id оставим null или возьмём первую модель
    config_result = await db.execute(select(LLMConfig).order_by(LLMConfig.sort_order, LLMConfig.created_at).limit(1))
    first_config = config_result.scalar_one_or_none()
    row = SystemLLMSettings(default_llm_config_id=first_config.id if first_config else None)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


# ---------- LLM Configs (модели) ----------


@router.get(
    "/llm-configs",
    response_model=list[LLMConfigResponse],
    status_code=status.HTTP_200_OK,
)
async def list_llm_configs(
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> list[LLMConfigResponse]:
    """Список всех настроенных моделей LLM."""
    result = await db.execute(select(LLMConfig).order_by(LLMConfig.sort_order, LLMConfig.created_at))
    configs = result.scalars().all()
    return [_llm_config_to_response(c) for c in configs]


@router.post(
    "/llm-configs",
    response_model=LLMConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_llm_config(
    payload: LLMConfigCreate,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> LLMConfigResponse:
    """Создать модель LLM."""
    row = LLMConfig(
        name=payload.name,
        provider=payload.provider.value,
        sort_order=payload.sort_order,
        gigachat_model=payload.gigachat_model,
        gigachat_scope=payload.gigachat_scope,
        gigachat_api_key_encrypted=payload.gigachat_api_key if payload.gigachat_api_key else None,
        external_base_url=payload.external_base_url,
        external_default_model=payload.external_default_model,
        external_timeout_seconds=payload.external_timeout_seconds,
        external_api_key_encrypted=payload.external_api_key if payload.external_api_key else None,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _llm_config_to_response(row)


@router.get(
    "/llm-configs/{config_id}",
    response_model=LLMConfigResponse,
    status_code=status.HTTP_200_OK,
)
async def get_llm_config(
    config_id: str,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> LLMConfigResponse:
    """Одна модель по id."""
    from uuid import UUID
    result = await db.execute(select(LLMConfig).where(LLMConfig.id == UUID(config_id)))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="LLM config not found")
    return _llm_config_to_response(row)


@router.patch(
    "/llm-configs/{config_id}",
    response_model=LLMConfigResponse,
    status_code=status.HTTP_200_OK,
)
async def update_llm_config(
  config_id: str,
  payload: LLMConfigUpdate,
  current_user: User = Depends(get_current_admin_user),
  db: AsyncSession = Depends(get_db),
) -> LLMConfigResponse:
    """Обновить модель."""
    from uuid import UUID
    result = await db.execute(select(LLMConfig).where(LLMConfig.id == UUID(config_id)))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="LLM config not found")
    if payload.name is not None:
        row.name = payload.name
    if payload.provider is not None:
        row.provider = payload.provider.value
    if payload.sort_order is not None:
        row.sort_order = payload.sort_order
    if payload.gigachat_model is not None:
        row.gigachat_model = payload.gigachat_model
    if payload.gigachat_scope is not None:
        row.gigachat_scope = payload.gigachat_scope
    if payload.gigachat_api_key is not None:
        row.gigachat_api_key_encrypted = payload.gigachat_api_key or None
    if payload.external_base_url is not None:
        row.external_base_url = payload.external_base_url
    if payload.external_default_model is not None:
        row.external_default_model = payload.external_default_model
    if payload.external_timeout_seconds is not None:
        row.external_timeout_seconds = payload.external_timeout_seconds
    if payload.external_api_key is not None:
        row.external_api_key_encrypted = payload.external_api_key or None
    if payload.temperature is not None:
        row.temperature = payload.temperature
    if payload.max_tokens is not None:
        row.max_tokens = payload.max_tokens
    await db.commit()
    await db.refresh(row)
    return _llm_config_to_response(row)


@router.delete(
    "/llm-configs/{config_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_llm_config(
  config_id: str,
  current_user: User = Depends(get_current_admin_user),
  db: AsyncSession = Depends(get_db),
) -> None:
    """Удалить модель. Запрещено, если она используется по умолчанию или в привязках агентов."""
    from uuid import UUID
    cid = UUID(config_id)
    sys_result = await db.execute(select(SystemLLMSettings).limit(1))
    sys_row = sys_result.scalar_one_or_none()
    if sys_row and sys_row.default_llm_config_id == cid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя удалить модель, выбранную по умолчанию. Сначала выберите другую модель.",
        )
    override_result = await db.execute(select(AgentLLMOverride).where(AgentLLMOverride.llm_config_id == cid).limit(1))
    if override_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя удалить модель, привязанную к агенту. Сначала снимите привязки.",
        )
    result = await db.execute(select(LLMConfig).where(LLMConfig.id == cid))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="LLM config not found")
    await db.delete(row)
    await db.commit()


# ---------- Системные настройки (default) ----------


@router.get(
    "/llm-settings",
    response_model=SystemLLMSettingsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_system_llm_settings(
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> SystemLLMSettingsResponse:
    """Системные настройки: default_llm_config_id, список моделей и привязок агентов."""
    settings = await _get_or_create_system_llm_settings(db)
    configs_result = await db.execute(select(LLMConfig).order_by(LLMConfig.sort_order, LLMConfig.created_at))
    configs = configs_result.scalars().all()
    overrides_result = await db.execute(select(AgentLLMOverride))
    overrides = overrides_result.scalars().all()
    return SystemLLMSettingsResponse(
        default_llm_config_id=settings.default_llm_config_id,
        configs=[_llm_config_to_response(c) for c in configs],
        agent_overrides=[
            {
                "agent_key": o.agent_key,
                "llm_config_id": str(o.llm_config_id),
                "runtime_options": o.runtime_options,
            }
            for o in overrides
        ],
    )


@router.patch(
    "/llm-settings",
    response_model=SystemLLMSettingsResponse,
    status_code=status.HTTP_200_OK,
)
async def update_system_llm_settings(
    payload: SystemLLMSettingsUpdate,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> SystemLLMSettingsResponse:
    """Установить модель по умолчанию."""
    settings = await _get_or_create_system_llm_settings(db)
    if payload.default_llm_config_id is not None:
        result = await db.execute(select(LLMConfig).where(LLMConfig.id == payload.default_llm_config_id))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="LLM config not found")
        settings.default_llm_config_id = payload.default_llm_config_id
    else:
        settings.default_llm_config_id = None
    await db.commit()
    await db.refresh(settings)
    configs_result = await db.execute(select(LLMConfig).order_by(LLMConfig.sort_order, LLMConfig.created_at))
    configs = configs_result.scalars().all()
    overrides_result = await db.execute(select(AgentLLMOverride))
    overrides = overrides_result.scalars().all()
    return SystemLLMSettingsResponse(
        default_llm_config_id=settings.default_llm_config_id,
        configs=[_llm_config_to_response(c) for c in configs],
        agent_overrides=[
            {
                "agent_key": o.agent_key,
                "llm_config_id": str(o.llm_config_id),
                "runtime_options": o.runtime_options,
            }
            for o in overrides
        ],
    )


# ---------- Привязки агентов ----------


@router.get(
    "/agent-llm-overrides",
    response_model=list[AgentLLMOverrideItem],
    status_code=status.HTTP_200_OK,
)
async def get_agent_llm_overrides(
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> list[AgentLLMOverrideItem]:
    """Список привязок агент → модель."""
    result = await db.execute(select(AgentLLMOverride))
    rows = result.scalars().all()
    return [
        AgentLLMOverrideItem(
            agent_key=o.agent_key,
            llm_config_id=o.llm_config_id,
            runtime_options=o.runtime_options,
        )
        for o in rows
    ]


@router.put(
    "/agent-llm-overrides",
    response_model=list[AgentLLMOverrideItem],
    status_code=status.HTTP_200_OK,
)
async def set_agent_llm_overrides(
    payload: AgentLLMOverridesSet,
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
) -> list[AgentLLMOverrideItem]:
    """Полная замена привязок. Передать список {agent_key, llm_config_id}."""
    # Проверить все llm_config_id
    for item in payload.overrides:
        r = await db.execute(select(LLMConfig).where(LLMConfig.id == item.llm_config_id))
        if not r.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"LLM config {item.llm_config_id} not found",
            )
    # Удалить старые, вставить новые
    await db.execute(delete(AgentLLMOverride))
    for item in payload.overrides:
        runtime_options = (
            item.runtime_options.model_dump(exclude_none=True)
            if item.runtime_options is not None
            else None
        )
        db.add(
            AgentLLMOverride(
                agent_key=item.agent_key,
                llm_config_id=item.llm_config_id,
                runtime_options=runtime_options,
            )
        )
    await db.commit()
    result = await db.execute(select(AgentLLMOverride))
    rows = result.scalars().all()
    return [
        AgentLLMOverrideItem(
            agent_key=o.agent_key,
            llm_config_id=o.llm_config_id,
            runtime_options=o.runtime_options,
        )
        for o in rows
    ]


# ---------- Тест LLM (по модели или default) ----------


async def _test_llm_config(db: AsyncSession, config: LLMConfig) -> UserAISettingsTestResponse:
    """Проверить подключение к одной модели."""
    provider = LLMProvider(config.provider)
    if provider == LLMProvider.GIGACHAT:
        api_key = config.gigachat_api_key_encrypted
        if not api_key:
            return UserAISettingsTestResponse(
                ok=False,
                provider=provider,
                message="Укажите API-ключ GigaChat в настройках модели (редактировать модель → поле API-ключ).",
                details={},
            )
        from app.services.gigachat_service import GigaChatService
        try:
            svc = GigaChatService(
                api_key=api_key,
                model=config.gigachat_model or "GigaChat",
                scope=config.gigachat_scope or "GIGACHAT_API_CORP",
            )
            reply = await svc.chat_completion(
                messages=[{"role": "user", "content": "Ответь одним словом: ОК"}],
                max_tokens=10,
            )
            return UserAISettingsTestResponse(
                ok=True,
                provider=provider,
                message="Подключение успешно. Ответ: " + (reply.strip()[:100] or "(пусто)"),
                details={"model": config.gigachat_model or "GigaChat"},
            )
        except Exception as e:
            return UserAISettingsTestResponse(ok=False, provider=provider, message=str(e), details={})

    api_key = config.external_api_key_encrypted
    if not api_key:
        return UserAISettingsTestResponse(
            ok=False,
            provider=provider,
            message="Укажите API-ключ внешнего провайдера в настройках модели.",
            details={},
        )
    base_url = (config.external_base_url or "https://api.openai.com/v1").rstrip("/")
    model = config.external_default_model or "gpt-4.1-mini"
    timeout_sec = config.external_timeout_seconds or 60
    from app.services.llm_router import OpenAICompatibleLLMClient, LLMCallParams, LLMMessage
    client = OpenAICompatibleLLMClient(
        base_url=base_url,
        api_key=api_key,
        model=model,
        timeout_seconds=timeout_sec,
    )
    try:
        reply = await client.chat_completion(
            LLMCallParams(messages=[LLMMessage(role="user", content="Reply with one word: OK")])
        )
        return UserAISettingsTestResponse(
            ok=True,
            provider=provider,
            message="Подключение успешно. Ответ: " + (reply.strip()[:100] or "(пусто)"),
            details={"model": model},
        )
    except httpx.HTTPStatusError as e:
        return UserAISettingsTestResponse(
            ok=False,
            provider=provider,
            message=f"HTTP {e.response.status_code}: {e.response.text[:200]}",
            details={},
        )
    except Exception as e:
        return UserAISettingsTestResponse(ok=False, provider=provider, message=str(e), details={})


@router.post(
    "/llm-settings/test",
    response_model=UserAISettingsTestResponse,
    status_code=status.HTTP_200_OK,
)
async def test_system_llm_settings(
    current_user: User = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
    llm_config_id: str | None = Query(None, description="ID модели для теста; если не указан — модель по умолчанию"),
) -> UserAISettingsTestResponse:
    """Проверить подключение к LLM. Без llm_config_id — тест модели по умолчанию."""
    if llm_config_id:
        from uuid import UUID
        result = await db.execute(select(LLMConfig).where(LLMConfig.id == UUID(llm_config_id)))
        config = result.scalar_one_or_none()
        if not config:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="LLM config not found")
    else:
        settings = await _get_or_create_system_llm_settings(db)
        if not settings.default_llm_config_id:
            return UserAISettingsTestResponse(
                ok=False,
                provider=LLMProvider.GIGACHAT,
                message="Не задана модель по умолчанию. Выберите модель в настройках или укажите llm_config_id для теста.",
                details={},
            )
        result = await db.execute(select(LLMConfig).where(LLMConfig.id == settings.default_llm_config_id))
        config = result.scalar_one_or_none()
        if not config:
            return UserAISettingsTestResponse(
                ok=False,
                provider=LLMProvider.GIGACHAT,
                message="Модель по умолчанию не найдена.",
                details={},
            )
    return await _test_llm_config(db, config)


@router.get(
    "/llm-settings/gigachat-models",
    response_model=list[GigaChatModelInfo],
    status_code=status.HTTP_200_OK,
)
async def get_system_gigachat_models(
    current_user: User = Depends(get_current_admin_user),
) -> list[GigaChatModelInfo]:
    """Список моделей GigaChat для выбора в настройках модели."""
    return [GigaChatModelInfo(**m) for m in GIGACHAT_MODELS]


# ---------- Playground ----------


def _build_playground_enriched_request(
    *,
    prompt: str,
    chat_history: list[dict],
) -> str:
    """Построить enriched user_request из истории и текущего сообщения."""
    enriched_request_lines: list[str] = []
    if chat_history:
        enriched_request_lines.append("История диалога (от старого к новому):")
        for msg in chat_history:
            role = msg.get("role", "user")
            content = (msg.get("content") or "").strip()
            if not content:
                continue
            prefix = "Пользователь" if role == "user" else "Ассистент"
            enriched_request_lines.append(f"- {prefix}: {content}")
    enriched_request_lines.append("\nТекущий вопрос пользователя:")
    enriched_request_lines.append(prompt.strip())
    return "\n".join(enriched_request_lines).strip()


@router.post(
    "/llm-playground/run",
    status_code=status.HTTP_200_OK,
)
async def run_llm_playground(
    payload: SystemLLMPlaygroundRunRequest,
    current_user: User = Depends(get_current_admin_user),
):
    """Запустить мультиагентный пайплайн в Playground. Используется системная конфигурация LLM."""
    from app.main import get_orchestrator
    orchestrator = get_orchestrator()
    if not orchestrator:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Orchestrator not available (Redis or GigaChat not initialized)",
        )
    try:
        chat_history = (payload.chat_history or [])[-10:]
        enriched_request = _build_playground_enriched_request(
            prompt=payload.prompt,
            chat_history=chat_history,
        )

        context: dict = {}
        if chat_history:
            context["chat_history"] = chat_history

        result = await orchestrator.process_request(
            user_request=enriched_request,
            board_id="playground",
            user_id=str(current_user.id),
            session_id=None,
            context=context,
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Playground run failed: {e}",
        )


@router.post(
    "/llm-playground/run-stream",
    status_code=status.HTTP_200_OK,
)
async def run_llm_playground_stream(
    payload: SystemLLMPlaygroundRunRequest,
    current_user: User = Depends(get_current_admin_user),
):
    """
    Streaming-версия Playground: отправляет progress-события и финальный result в формате NDJSON.
    """
    from app.main import get_orchestrator

    orchestrator = get_orchestrator()
    if not orchestrator:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Orchestrator not available (Redis or GigaChat not initialized)",
        )

    chat_history = (payload.chat_history or [])[-10:]
    enriched_request = _build_playground_enriched_request(
        prompt=payload.prompt,
        chat_history=chat_history,
    )
    context: dict = {}
    if chat_history:
        context["chat_history"] = chat_history

    queue: asyncio.Queue[dict] = asyncio.Queue()

    async def _progress_callback(progress_payload: dict) -> None:
        payload = progress_payload or {}
        if payload.get("event") == "plan_update":
            await queue.put({
                "type": "plan",
                "steps": payload.get("steps") or [],
                "completed_count": payload.get("completed_count") or 0,
                "source": payload.get("source"),
            })
            return
        await queue.put({
            "type": "progress",
            **payload,
        })

    async def _run_orchestrator() -> None:
        try:
            await queue.put({"type": "start"})
            result = await orchestrator.process_request(
                user_request=enriched_request,
                board_id="playground",
                user_id=str(current_user.id),
                session_id=None,
                context={
                    **context,
                    "_progress_callback": _progress_callback,
                    "_enable_plan_progress": True,
                },
            )
            await queue.put({"type": "result", "result": result})
        except Exception as e:
            await queue.put({"type": "error", "error": f"Playground run failed: {e}"})
        finally:
            await queue.put({"type": "done"})

    async def _event_stream():
        task = asyncio.create_task(_run_orchestrator())
        try:
            while True:
                item = await queue.get()
                yield json.dumps(item, ensure_ascii=False) + "\n"
                if item.get("type") == "done":
                    break
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(_event_stream(), media_type="application/x-ndjson")
