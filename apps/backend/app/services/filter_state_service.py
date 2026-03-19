"""Filter state service for active board/dashboard filters.

Provides backend-side API to manage active filters in one place so it can be
used both from HTTP routes and internal backend flows.
"""
from __future__ import annotations

from datetime import datetime
from copy import deepcopy
from difflib import SequenceMatcher
from typing import Any


class FilterStateService:
    """In-memory active filter state (MVP).

    NOTE: For production, replace with Redis-backed implementation.
    """

    _active_filters_store: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _filter_key(scope: str, target_id: str, user_id: str) -> str:
        return f"{scope}:{target_id}:{user_id}"

    @classmethod
    def get_active_filters(
        cls,
        *,
        scope: str,
        target_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        key = cls._filter_key(scope, target_id, user_id)
        return cls._active_filters_store.get(key, {})

    @classmethod
    def set_active_filters(
        cls,
        *,
        scope: str,
        target_id: str,
        user_id: str,
        filters: dict[str, Any] | None,
        preset_id: str | None = None,
    ) -> dict[str, Any]:
        key = cls._filter_key(scope, target_id, user_id)
        payload = {
            "filters": filters,
            "preset_id": preset_id,
            "updated_at": datetime.utcnow(),
        }
        cls._active_filters_store[key] = payload
        return payload

    @classmethod
    def clear_active_filters(
        cls,
        *,
        scope: str,
        target_id: str,
        user_id: str,
    ) -> None:
        key = cls._filter_key(scope, target_id, user_id)
        cls._active_filters_store.pop(key, None)

    @classmethod
    def add_filter_json_object(
        cls,
        *,
        scope: str,
        target_id: str,
        user_id: str,
        filter_json: dict[str, Any],
        dim_known_values: dict[str, list[str]] | None = None,
        fuzzy_threshold: float = 0.84,
    ) -> dict[str, Any]:
        """Backend-side addFilter(jsonObject).

        The incoming jsonObject is treated as full FilterExpression and becomes
        the active filter for the given scope/target/user.
        """
        normalized_filter = cls.normalize_filter_json_typo_tolerant(
            filter_json=filter_json,
            dim_known_values=dim_known_values or {},
            fuzzy_threshold=fuzzy_threshold,
        )
        return cls.set_active_filters(
            scope=scope,
            target_id=target_id,
            user_id=user_id,
            filters=normalized_filter,
            preset_id=None,
        )

    @classmethod
    def normalize_filter_json_typo_tolerant(
        cls,
        *,
        filter_json: dict[str, Any],
        dim_known_values: dict[str, list[str]],
        fuzzy_threshold: float = 0.84,
    ) -> dict[str, Any]:
        """Normalize string values in FilterExpression using known dim values.

        Supports recursive condition/group expressions. Only string-like values
        are normalized. Unknown dimensions are passed through unchanged.
        """
        expr = deepcopy(filter_json or {})
        if not isinstance(expr, dict):
            return filter_json
        cls._normalize_expr_inplace(
            expr=expr,
            dim_known_values=dim_known_values,
            fuzzy_threshold=fuzzy_threshold,
        )
        return expr

    @classmethod
    def _normalize_expr_inplace(
        cls,
        *,
        expr: dict[str, Any],
        dim_known_values: dict[str, list[str]],
        fuzzy_threshold: float,
    ) -> None:
        et = str(expr.get("type", "")).lower()
        if et in ("and", "or"):
            conds = expr.get("conditions", [])
            if isinstance(conds, list):
                for item in conds:
                    if isinstance(item, dict):
                        cls._normalize_expr_inplace(
                            expr=item,
                            dim_known_values=dim_known_values,
                            fuzzy_threshold=fuzzy_threshold,
                        )
            return

        if et != "condition":
            return

        dim = str(expr.get("dim", "")).strip()
        op = str(expr.get("op", "")).strip()
        if not dim:
            return

        known_values = dim_known_values.get(dim) or dim_known_values.get(dim.lower()) or []
        if not known_values:
            return

        value = expr.get("value")
        if op in ("==", "!=", "contains", "starts_with") and isinstance(value, str):
            resolved = cls._resolve_string_value(value, known_values, fuzzy_threshold)
            if resolved:
                expr["value"] = resolved
            return

        if op in ("in", "not_in") and isinstance(value, list):
            out: list[Any] = []
            for item in value:
                if isinstance(item, str):
                    resolved = cls._resolve_string_value(item, known_values, fuzzy_threshold)
                    out.append(resolved if resolved else item)
                else:
                    out.append(item)
            expr["value"] = out

    @staticmethod
    def _resolve_string_value(
        raw_value: str,
        known_values: list[str],
        fuzzy_threshold: float,
    ) -> str | None:
        src = str(raw_value).strip()
        if not src:
            return None

        src_l = src.lower()
        prepared = [str(v).strip() for v in known_values if str(v).strip()]
        if not prepared:
            return None

        # 1) Exact (case-insensitive)
        for cand in prepared:
            if cand.lower() == src_l:
                return cand

        # 2) Substring compatibility for contains-like inputs
        for cand in prepared:
            cand_l = cand.lower()
            if src_l in cand_l or cand_l in src_l:
                return cand

        # 3) Fuzzy match
        best: str | None = None
        best_ratio = 0.0
        for cand in prepared:
            ratio = SequenceMatcher(None, src_l, cand.lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best = cand

        if best is not None and best_ratio >= fuzzy_threshold:
            return best
        return None

