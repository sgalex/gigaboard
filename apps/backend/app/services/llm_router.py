"""
Маршрутизатор LLM-запросов. Использует настроенные модели (llm_config), модель по умолчанию
и привязки агентов (agent_llm_override). См. docs/LLM_CONFIGURATION_CONCEPT.md.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, replace as dc_replace
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SystemLLMSettings, LLMConfig, AgentLLMOverride
from app.schemas import LLMProvider
from app.services.gigachat_service import GigaChatService

logger = logging.getLogger(__name__)


@dataclass
class LLMMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMCallParams:
    messages: List[LLMMessage]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class OpenAICompatibleLLMClient:
    """
    Клиент для OpenAI-совместимого Chat Completions API (v1).
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: int = 60,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    def _build_messages(self, params: LLMCallParams) -> List[Dict[str, str]]:
        return [{"role": m.role, "content": m.content} for m in params.messages]

    async def chat_completion(self, params: LLMCallParams) -> str:
        import httpx
        url = f"{self.base_url}/chat/completions"
        body: Dict[str, Any] = {
            "model": self.model,
            "messages": self._build_messages(params),
        }
        if params.temperature is not None:
            body["temperature"] = params.temperature
        if params.max_tokens is not None:
            body["max_tokens"] = params.max_tokens

        async with httpx.AsyncClient(timeout=float(self.timeout_seconds)) as client:
            resp = await client.post(
                url,
                json=body,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("OpenAI-compatible API returned no choices")
        message = choices[0].get("message") or {}
        return message.get("content") or ""


class LLMRouter:
    """
    Маршрутизатор LLM-запросов. Выбор модели: по привязке агента (agent_key)
    или модель по умолчанию. См. docs/LLM_CONFIGURATION_CONCEPT.md.

    Зарезервированные ключи кроме имён агентов (planner, analyst, …):
    ``context_graph_compression`` — сжатие уровней контекстного графа (L1/L2);
    настраивается в тех же привязках ``agent_llm_override``, что и агенты.
    См. ``multi_agent.context_graph.constants.CONTEXT_GRAPH_COMPRESSION_AGENT_KEY``.
    """

    def __init__(
        self,
        gigachat_service: Optional[GigaChatService] = None,
        db_session_factory: Optional[Callable[[], AsyncSession]] = None,
    ) -> None:
        self._gigachat = gigachat_service
        self._db_session_factory = db_session_factory

    @staticmethod
    def _is_auth_or_permission_error(exc: BaseException) -> bool:
        """Определяет ошибки доступа провайдера (401/403)."""
        if isinstance(exc, httpx.HTTPStatusError):
            status = getattr(exc.response, "status_code", None)
            return status in (401, 403)
        return False

    def _get_gigachat_from_config(self, config: LLMConfig) -> Optional[GigaChatService]:
        """Ключ и параметры только из настроек модели (без env)."""
        api_key = config.gigachat_api_key_encrypted
        if not api_key:
            return None
        model = config.gigachat_model or "GigaChat"
        scope = config.gigachat_scope or "GIGACHAT_API_CORP"
        return GigaChatService(api_key=api_key, model=model, scope=scope)

    def _get_openai_client_from_config(
        self,
        config: LLMConfig,
    ) -> Optional[OpenAICompatibleLLMClient]:
        api_key = config.external_api_key_encrypted
        if not api_key:
            return None
        base_url = (config.external_base_url or "https://api.openai.com/v1").rstrip("/")
        model = config.external_default_model or "gpt-4.1-mini"
        timeout = config.external_timeout_seconds or 60
        return OpenAICompatibleLLMClient(
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout_seconds=timeout,
        )

    async def _resolve_llm_config(
        self,
        db: AsyncSession,
        agent_key: Optional[str] = None,
    ) -> Optional[LLMConfig]:
        """
        Определить пресет LLM: привязка по agent_key или system_llm_settings.default_llm_config_id.

        Одинаково для имён агентов (planner, …) и служебных ключей (context_graph_compression):
        если записи в agent_llm_override нет — используется модель по умолчанию.
        """
        sys_result = await db.execute(select(SystemLLMSettings).limit(1))
        sys_row = sys_result.scalar_one_or_none()
        if not sys_row:
            return None

        llm_config_id: Optional[UUID] = None
        if agent_key:
            override_result = await db.execute(
                select(AgentLLMOverride).where(AgentLLMOverride.agent_key == agent_key)
            )
            override = override_result.scalar_one_or_none()
            if override:
                llm_config_id = override.llm_config_id
        if llm_config_id is None:
            llm_config_id = sys_row.default_llm_config_id
        if not llm_config_id:
            return None

        config_result = await db.execute(select(LLMConfig).where(LLMConfig.id == llm_config_id))
        return config_result.scalar_one_or_none()

    async def get_agent_runtime_options_map(self) -> Dict[str, Dict[str, Any]]:
        """
        Возвращает runtime_options по агентам из agent_llm_override.
        Используется оркестратором для task policies (timeout/retries/context budget).
        """
        if not self._db_session_factory:
            return {}
        async with self._db_session_factory() as db:
            result = await db.execute(select(AgentLLMOverride))
            rows = result.scalars().all()
            options_map: Dict[str, Dict[str, Any]] = {}
            for row in rows:
                if not isinstance(row.runtime_options, dict):
                    continue
                options_map[row.agent_key] = row.runtime_options
            return options_map

    async def chat_completion(
        self,
        *,
        user_id: Optional[UUID],
        params: LLMCallParams,
        agent_key: Optional[str] = None,
    ) -> str:
        """
        Выполняет чат-запрос. Модель выбирается по agent_key (привязка агента)
        или по умолчанию. При отсутствии модели возвращается ошибка с подсказкой
        настроить модель в панели администратора.
        """
        messages_dict = [m.__dict__ for m in params.messages]
        temp = params.temperature
        max_tok = params.max_tokens

        if self._db_session_factory:
            async with self._db_session_factory() as db:
                config = await self._resolve_llm_config(db, agent_key=agent_key)
                if config:
                    if config.provider == LLMProvider.GIGACHAT.value:
                        gigachat_svc = self._get_gigachat_from_config(config)
                        if gigachat_svc:
                            t = temp if temp is not None else config.temperature
                            m = max_tok if max_tok is not None else config.max_tokens
                            return await gigachat_svc.chat_completion(
                                messages=messages_dict,
                                temperature=t,
                                max_tokens=m,
                            )
                    elif config.provider == LLMProvider.EXTERNAL_OPENAI_COMPAT.value:
                        client = self._get_openai_client_from_config(config)
                        if client:
                            t = temp if temp is not None else config.temperature
                            m = max_tok if max_tok is not None else config.max_tokens
                            p = dc_replace(params, temperature=t, max_tokens=m)
                            try:
                                return await client.chat_completion(p)
                            except Exception as e:
                                if self._gigachat and self._is_auth_or_permission_error(e):
                                    logger.warning(
                                        "External LLM returned auth/permission error for agent=%s; "
                                        "fallback to internal GigaChat",
                                        agent_key,
                                    )
                                    return await self._gigachat.chat_completion(
                                        messages=messages_dict,
                                        temperature=t,
                                        max_tokens=m,
                                    )
                                raise
                    logger.warning(
                        "LLM config %s has no valid credentials (укажите API-ключ в настройках модели)",
                        config.id,
                    )

        if self._gigachat:
            return await self._gigachat.chat_completion(
                messages=messages_dict,
                temperature=temp,
                max_tokens=max_tok,
            )
        raise RuntimeError(
            "LLM не настроен: выберите модель по умолчанию в панели администратора (Профиль → Настройки LLM) "
            "и укажите API-ключ в настройках модели."
        )
