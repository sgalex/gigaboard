"""
Переопределения multi-agent на время запроса.

Приоритет: значения из профиля пользователя (user_ai_settings.multi_agent_settings)
→ переменные окружения MULTI_AGENT_* → дефолты в коде.

См. docs/MULTI_AGENT_SYSTEM.md
"""
from __future__ import annotations

import os
from contextvars import ContextVar, Token
from typing import Any, Dict, List, Optional
from uuid import UUID

_MA_OVERRIDES: ContextVar[Optional[Dict[str, Any]]] = ContextVar(
    "multi_agent_overrides", default=None
)


def get_active_overrides() -> Dict[str, Any]:
    o = _MA_OVERRIDES.get()
    return dict(o) if o else {}


def _raw_for_key(name: str) -> Optional[str]:
    ov = _MA_OVERRIDES.get()
    if not ov or name not in ov:
        return None
    v = ov[name]
    if v is None:
        return None
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v).strip()


def ma_int(name: str, default: int) -> int:
    raw = _raw_for_key(name)
    if raw is None:
        raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError:
        return default


def ma_str(name: str, default: str = "") -> str:
    raw = _raw_for_key(name)
    if raw is None:
        return os.getenv(name, default).strip()
    return raw


def ma_bool(name: str, default: bool) -> bool:
    raw = _raw_for_key(name)
    if raw is None:
        raw = os.getenv(name, "true" if default else "false").strip()
    return raw.lower() in ("1", "true", "yes", "on")


def set_ma_overrides_token(overrides: Dict[str, Any]) -> Token:
    return _MA_OVERRIDES.set(overrides)


def reset_ma_overrides_token(token: Token) -> None:
    _MA_OVERRIDES.reset(token)


async def load_user_multi_agent_overrides(
    db_session_factory: Any,
    user_id: Optional[str],
) -> Dict[str, Any]:
    if not db_session_factory or not user_id:
        return {}
    try:
        uid = UUID(str(user_id))
    except (ValueError, TypeError):
        return {}
    from sqlalchemy import select

    from app.models import UserAISettings

    async with db_session_factory() as session:
        result = await session.execute(
            select(UserAISettings).where(UserAISettings.user_id == uid)
        )
        row = result.scalar_one_or_none()
        if not row or not row.multi_agent_settings:
            return {}
        data = row.multi_agent_settings
        return data if isinstance(data, dict) else {}


def ladder_from_env(name: str, default: List[str]) -> List[str]:
    raw = ma_str(name, "").strip()
    if not raw:
        return default
    levels = [item.strip().lower() for item in raw.split(",") if item.strip()]
    valid = [lvl for lvl in levels if lvl in {"full", "compact", "minimal"}]
    return valid or default
