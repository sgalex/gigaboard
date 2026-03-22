import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core import get_db
from app.middleware import get_current_user
from app.models import User, UserAISettings, UserSecret
from app.schemas import (
    UserAISettingsResponse,
    UserAISettingsUpdate,
    UserAISettingsTestRequest,
    UserAISettingsTestResponse,
    LLMProvider,
    GigaChatModelInfo,
)

router = APIRouter(prefix="/api/v1/users/me", tags=["user-settings"])

# Список моделей GigaChat для выбора в профиле (актуальный на момент реализации)
GIGACHAT_MODELS: list[dict[str, str]] = [
    {"id": "GigaChat", "name": "GigaChat", "description": "Базовая модель"},
    {"id": "GigaChat-Pro", "name": "GigaChat-Pro", "description": "Продвинутая модель"},
    {"id": "GigaChat-Max", "name": "GigaChat-Max", "description": "Максимальные возможности"},
    {"id": "GigaChat-Mini", "name": "GigaChat-Mini", "description": "Облегчённая модель"},
]


async def _get_or_create_ai_settings(db: AsyncSession, user: User) -> UserAISettings:
    result = await db.execute(
        select(UserAISettings).where(UserAISettings.user_id == user.id)
    )
    settings = result.scalar_one_or_none()
    if settings:
        return settings

    settings = UserAISettings(user_id=user.id, provider="gigachat")
    db.add(settings)
    await db.commit()
    await db.refresh(settings)
    return settings


def _is_admin(user: User) -> bool:
    return getattr(user, "role", None) == "admin"


def _build_response(settings: UserAISettings, *, viewer: User) -> UserAISettingsResponse:
    ma = settings.multi_agent_settings if _is_admin(viewer) else None
    return UserAISettingsResponse(
        user_id=settings.user_id,
        provider=LLMProvider(settings.provider),
        gigachat_model=settings.gigachat_model,
        gigachat_scope=settings.gigachat_scope,
        has_gigachat_api_key=settings.gigachat_api_key_secret_id is not None,
        external_base_url=settings.external_base_url,
        external_default_model=settings.external_default_model,
        external_timeout_seconds=settings.external_timeout_seconds,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        has_external_api_key=settings.external_api_key_secret_id is not None,
        preferred_style=settings.preferred_style,
        multi_agent_settings=ma,
    )


@router.get(
    "/ai-settings",
    response_model=UserAISettingsResponse,
    status_code=status.HTTP_200_OK,
)
async def get_ai_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserAISettingsResponse:
    """
    Получить текущие AI/LLM-настройки пользователя.

    Если настройки ещё не созданы, возвращаются дефолтные значения (provider=gigachat).
    """
    settings = await _get_or_create_ai_settings(db, current_user)
    return _build_response(settings, viewer=current_user)


@router.get(
    "/ai-settings/gigachat-models",
    response_model=list[GigaChatModelInfo],
    status_code=status.HTTP_200_OK,
)
async def get_gigachat_models() -> list[GigaChatModelInfo]:
    """
    Список доступных моделей GigaChat для выбора в настройках.
    """
    return [GigaChatModelInfo(**m) for m in GIGACHAT_MODELS]


@router.put(
    "/ai-settings",
    response_model=UserAISettingsResponse,
    status_code=status.HTTP_200_OK,
)
async def update_ai_settings(
    payload: UserAISettingsUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserAISettingsResponse:
    """
    Обновить AI/LLM-настройки пользователя.

    - При передаче external_api_key создаётся/обновляется UserSecret.
    - В ответе никогда не возвращается сам API-ключ, только флаг has_external_api_key.
    """
    settings = await _get_or_create_ai_settings(db, current_user)

    settings.provider = payload.provider.value

    # GigaChat
    settings.gigachat_model = payload.gigachat_model
    settings.gigachat_scope = payload.gigachat_scope

    # Обновление/создание секрета для GigaChat API ключа
    if payload.gigachat_api_key:
        secret: UserSecret | None = None
        if settings.gigachat_api_key_secret_id:
            result = await db.execute(
                select(UserSecret).where(
                    UserSecret.id == settings.gigachat_api_key_secret_id,
                    UserSecret.user_id == current_user.id,
                )
            )
            secret = result.scalar_one_or_none()
        if not secret:
            secret = UserSecret(
                user_id=current_user.id,
                type="gigachat_api_key",
                provider="gigachat",
                encrypted_value=payload.gigachat_api_key,
            )
            db.add(secret)
            await db.flush()
            settings.gigachat_api_key_secret_id = secret.id
        else:
            secret.encrypted_value = payload.gigachat_api_key

    # Внешний провайдер
    if payload.external_base_url is not None:
        settings.external_base_url = payload.external_base_url
    if payload.external_default_model is not None:
        settings.external_default_model = payload.external_default_model
    if payload.external_timeout_seconds is not None:
        settings.external_timeout_seconds = payload.external_timeout_seconds

    # Общие параметры генерации
    if payload.temperature is not None:
        settings.temperature = payload.temperature
    if payload.max_tokens is not None:
        settings.max_tokens = payload.max_tokens

    # Произвольные предпочтения
    if payload.preferred_style is not None:
        settings.preferred_style = payload.preferred_style

    update_data = payload.model_dump(exclude_unset=True)
    if "multi_agent_settings" in update_data:
        if not _is_admin(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="multi_agent_settings доступны только администратору",
            )
        settings.multi_agent_settings = payload.multi_agent_settings

    # Обновление/создание секрета для внешнего LLM
    if payload.external_api_key:
        if not settings.external_base_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="external_base_url must be set before saving external_api_key",
            )
        provider_hint = None
        if "openai" in settings.external_base_url:
            provider_hint = "openai"

        secret: UserSecret | None = None
        if settings.external_api_key_secret_id:
            result = await db.execute(
                select(UserSecret).where(
                    UserSecret.id == settings.external_api_key_secret_id,
                    UserSecret.user_id == current_user.id,
                )
            )
            secret = result.scalar_one_or_none()

        if not secret:
            secret = UserSecret(
                user_id=current_user.id,
                type="external_llm_api_key",
                provider=provider_hint,
                encrypted_value=payload.external_api_key,
            )
            db.add(secret)
            await db.flush()
            settings.external_api_key_secret_id = secret.id
        else:
            secret.encrypted_value = payload.external_api_key
            if provider_hint:
                secret.provider = provider_hint

    await db.commit()
    await db.refresh(settings)
    return _build_response(settings, viewer=current_user)


@router.post(
    "/ai-settings/test",
    response_model=UserAISettingsTestResponse,
    status_code=status.HTTP_200_OK,
)
async def test_ai_settings(
    payload: UserAISettingsTestRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserAISettingsTestResponse:
    """
    Тест подключения к выбранному LLM-провайдеру.

    На MVP-этапе:
    - Для GigaChat проверяется только базовая доступность (по системной конфигурации).
    - Для внешнего OpenAI-совместимого провайдера возвращается успешный результат,
      если указан base_url и есть API-ключ (в запросе или уже сохранённый).
    """
    settings = await _get_or_create_ai_settings(db, current_user)

    provider = payload.provider or LLMProvider(settings.provider)

    if provider == LLMProvider.GIGACHAT:
        effective_model = (
            payload.gigachat_model
            or settings.gigachat_model
            or "GigaChat"
        )
        effective_scope = (
            payload.gigachat_scope
            or settings.gigachat_scope
            or "GIGACHAT_API_CORP"
        )
        api_key = payload.gigachat_api_key
        if not api_key and settings.gigachat_api_key_secret_id:
            result = await db.execute(
                select(UserSecret).where(
                    UserSecret.id == settings.gigachat_api_key_secret_id,
                    UserSecret.user_id == current_user.id,
                )
            )
            secret = result.scalar_one_or_none()
            if secret:
                api_key = secret.encrypted_value
        if api_key:
            from app.services.gigachat_service import GigaChatService
            try:
                svc = GigaChatService(
                    api_key=api_key,
                    model=effective_model,
                    scope=effective_scope,
                )
                reply = await svc.chat_completion(
                    messages=[{"role": "user", "content": "Ответь одним словом: ОК"}],
                    max_tokens=10,
                )
                return UserAISettingsTestResponse(
                    ok=True,
                    provider=provider,
                    message="Подключение успешно. Ответ: " + (reply.strip()[:100] or "(пусто)"),
                    details={"model": effective_model, "scope": effective_scope},
                )
            except Exception as e:
                return UserAISettingsTestResponse(
                    ok=False,
                    provider=provider,
                    message=str(e),
                    details={"model": effective_model, "scope": effective_scope},
                )
        # Нет пользовательского ключа — проверка системного (если настроен)
        try:
            from app.services.gigachat_service import get_gigachat_service
            sys_svc = get_gigachat_service()
            if sys_svc:
                await sys_svc.chat_completion(
                    messages=[{"role": "user", "content": "Ответь: ОК"}],
                    max_tokens=10,
                )
                return UserAISettingsTestResponse(
                    ok=True,
                    provider=provider,
                    message="Используется системный ключ GigaChat. Подключение успешно.",
                    details={"model": effective_model},
                )
        except Exception as e:
            return UserAISettingsTestResponse(
                ok=False,
                provider=provider,
                message="Системный ключ не настроен или ошибка: " + str(e),
                details={},
            )
        return UserAISettingsTestResponse(
            ok=True,
            provider=provider,
            message="GigaChat: укажите свой API-ключ в настройках или попросите администратора настроить модель GigaChat в панели администратора.",
            details={},
        )

    # Внешний OpenAI-совместимый провайдер
    effective_base_url = (
        payload.external_base_url
        or settings.external_base_url
        or "https://api.openai.com/v1"
    )
    effective_model = (
        payload.external_default_model
        or settings.external_default_model
        or "gpt-4.1-mini"
    )

    # API-ключ: приоритет у значения из запроса, затем — сохранённого секрета
    api_key = payload.external_api_key
    if not api_key and settings.external_api_key_secret_id:
        result = await db.execute(
            select(UserSecret).where(
                UserSecret.id == settings.external_api_key_secret_id,
                UserSecret.user_id == current_user.id,
            )
        )
        secret = result.scalar_one_or_none()
        if secret:
            api_key = secret.encrypted_value

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="external_api_key is required for testing external provider",
        )

    if not effective_base_url.startswith("http"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="external_base_url must be a valid HTTP(S) URL",
        )

    # Реальный тестовый вызов к внешнему API
    from app.services.llm_router import OpenAICompatibleLLMClient, LLMCallParams, LLMMessage

    timeout_sec = (
        payload.external_timeout_seconds
        or settings.external_timeout_seconds
        or 60
    )
    client = OpenAICompatibleLLMClient(
        base_url=effective_base_url,
        api_key=api_key,
        model=effective_model,
        timeout_seconds=timeout_sec,
    )
    try:
        response_text = await client.chat_completion(
            LLMCallParams(
                messages=[LLMMessage(role="user", content="Say exactly: GigaBoard OK")],
                max_tokens=50,
            )
        )
        return UserAISettingsTestResponse(
            ok=True,
            provider=LLMProvider.EXTERNAL_OPENAI_COMPAT,
            message="Подключение успешно. Ответ модели: " + (response_text.strip()[:200] or "(пусто)"),
            details={
                "base_url": effective_base_url,
                "model": effective_model,
                "timeout_seconds": timeout_sec,
            },
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Внешний API вернул ошибку: {e.response.status_code}",
        )
    except Exception as e:
        return UserAISettingsTestResponse(
            ok=False,
            provider=LLMProvider.EXTERNAL_OPENAI_COMPAT,
            message=str(e),
            details={"base_url": effective_base_url, "model": effective_model},
        )

