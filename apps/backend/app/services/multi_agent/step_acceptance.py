"""
Per-step acceptance: детерминированная проверка результата агента на минимальное
соответствие роли шага (после успешного execute_step).

Не заменяет финальный QualityGate; даёт раннюю сигнализацию в trace и pipeline_memory.
См. docs/MULTI_AGENT.md (раздел про step acceptance и таблицу критериев).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Tuple

from .runtime_overrides import ma_bool


Level = Literal["ok", "warn", "fail"]

Issue = Tuple[str, str]

# Пороги длины текста (символы после strip)
MIN_ANALYST_NARRATIVE_SOFT = 20
MIN_DISCOVERY_NARRATIVE_SOFT = 24
MIN_RESEARCH_NARRATIVE_SOFT = 40
MIN_REPORTER_NARRATIVE_SOFT = 16


@dataclass
class StepAcceptanceResult:
    """Итог проверки шага."""

    level: Level
    codes: List[str] = field(default_factory=list)
    messages: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.level != "fail"

    def to_trace_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "level": self.level,
            "codes": list(self.codes),
            "messages": list(self.messages),
        }


def normalize_step_acceptance_agent_name(agent_name: str) -> str:
    """Синонимы из старых планов / логов → ключи, совпадающие с agent_name в AgentPayload."""
    n = str(agent_name or "").strip()
    if n == "codex":
        return "transform_codex"
    return n


def _narrative_text(result: Dict[str, Any]) -> str:
    n = result.get("narrative")
    if isinstance(n, dict):
        return str(n.get("text") or "").strip()
    if isinstance(n, str):
        return n.strip()
    return ""


def _has_non_empty_findings(result: Dict[str, Any]) -> bool:
    for f in result.get("findings") or []:
        if not isinstance(f, dict):
            continue
        if str(f.get("text") or "").strip():
            return True
    return False


def _non_empty_finding_count(result: Dict[str, Any]) -> int:
    n = 0
    for f in result.get("findings") or []:
        if isinstance(f, dict) and str(f.get("text") or "").strip():
            n += 1
    return n


def _has_code_blocks(result: Dict[str, Any]) -> bool:
    for cb in result.get("code_blocks") or []:
        if isinstance(cb, dict) and str(cb.get("code") or "").strip():
            return True
    return False


def _has_tables(result: Dict[str, Any]) -> bool:
    tables = result.get("tables") or []
    return isinstance(tables, list) and len(tables) > 0


def _table_has_substance(t: Dict[str, Any]) -> bool:
    """Таблица считается непустой, если есть колонки, строки или положительный row_count."""
    if not isinstance(t, dict):
        return False
    cols = t.get("columns") or []
    rows = t.get("rows") or []
    rc = t.get("row_count")
    if isinstance(rc, (int, float)) and int(rc) > 0:
        return True
    if isinstance(rows, list) and len(rows) > 0:
        return True
    if isinstance(cols, list) and len(cols) > 0:
        return True
    return False


def _structurizer_tables_substance(result: Dict[str, Any]) -> Tuple[int, int]:
    """Число таблиц всего и число таблиц с «телом» (колонки/строки/row_count)."""
    tables = result.get("tables") or []
    if not isinstance(tables, list):
        return 0, 0
    total = len(tables)
    good = sum(1 for t in tables if isinstance(t, dict) and _table_has_substance(t))
    return total, good


def _has_discovery_signals(result: Dict[str, Any]) -> bool:
    if _narrative_text(result):
        return True
    src = result.get("sources") or []
    if isinstance(src, list) and len(src) > 0:
        return True
    dr = result.get("discovered_resources") or []
    return isinstance(dr, list) and len(dr) > 0


def _sources_with_url_count(result: Dict[str, Any]) -> int:
    n = 0
    for s in result.get("sources") or []:
        if isinstance(s, dict) and str(s.get("url") or "").strip():
            n += 1
    return n


def _fetched_sources_count(result: Dict[str, Any]) -> int:
    n = 0
    for s in result.get("sources") or []:
        if not isinstance(s, dict):
            continue
        if s.get("fetched") is True:
            n += 1
    return n


def _has_research_signals(result: Dict[str, Any]) -> bool:
    if _narrative_text(result):
        return True
    for s in result.get("sources") or []:
        if isinstance(s, dict) and (str(s.get("url") or "").strip() or s.get("fetched")):
            return True
    return False


def _validation_dict(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    v = result.get("validation")
    return v if isinstance(v, dict) else None


def _codex_syntax_soft_issues(agent_name: str, result: Dict[str, Any]) -> List[Issue]:
    soft: List[Issue] = []
    blocks = [b for b in (result.get("code_blocks") or []) if isinstance(b, dict)]
    if not blocks:
        return soft
    bad = [b for b in blocks if b.get("syntax_valid") is False]
    if bad:
        soft.append(
            (
                "codex_syntax_invalid",
                f"{agent_name}: syntax_valid=false у {len(bad)} блок(ов) code_blocks",
            )
        )
    langs = {str(b.get("language") or "").lower() for b in blocks}
    langs.discard("")
    if (
        agent_name == "widget_codex"
        and langs
        and not (langs & {"html", "javascript"})
    ):
        soft.append(
            (
                "widget_codex_language_mismatch",
                "widget_codex: в code_blocks указан language не html/javascript",
            )
        )
    if (
        agent_name == "transform_codex"
        and langs
        and "python" not in langs
    ):
        soft.append(
            (
                "transform_codex_language_mismatch",
                "transform_codex: в code_blocks нет блока с language=python",
            )
        )
    return soft


def _evaluate_reporter(result: Dict[str, Any]) -> Tuple[List[Issue], List[Issue]]:
    critical: List[Issue] = []
    soft: List[Issue] = []
    nar = _narrative_text(result)
    has_tab = _has_tables(result)
    if not nar and not has_tab:
        critical.append(
            ("reporter_empty_output", "reporter: нет narrative и нет tables при success"),
        )
    elif not nar and has_tab:
        soft.append(
            ("reporter_tables_only", "reporter: есть только tables, без narrative"),
        )
    elif nar and len(nar) < MIN_REPORTER_NARRATIVE_SOFT and not has_tab:
        soft.append(
            (
                "reporter_very_short_narrative",
                f"reporter: narrative короче {MIN_REPORTER_NARRATIVE_SOFT} символов и нет tables",
            ),
        )
    return critical, soft


def _evaluate_codex(agent_name: str, result: Dict[str, Any]) -> Tuple[List[Issue], List[Issue]]:
    critical: List[Issue] = []
    soft: List[Issue] = []
    if not _has_code_blocks(result):
        critical.append(
            ("codex_no_code", f"{agent_name}: success без непустого code_blocks"),
        )
    else:
        soft.extend(_codex_syntax_soft_issues(agent_name, result))
        nar = _narrative_text(result)
        if nar and len(nar) < 12:
            soft.append(
                (
                    "codex_thin_narrative",
                    f"{agent_name}: очень короткий narrative при наличии кода",
                ),
            )
    return critical, soft


def _evaluate_structurizer(result: Dict[str, Any]) -> Tuple[List[Issue], List[Issue]]:
    critical: List[Issue] = []
    soft: List[Issue] = []
    nar = _narrative_text(result)
    total, good = _structurizer_tables_substance(result)
    if total == 0 and not nar:
        soft.append(
            (
                "structurizer_no_tables",
                "structurizer: нет tables и пустой narrative — проверьте извлечение",
            ),
        )
    elif total > 0 and good == 0:
        soft.append(
            (
                "structurizer_tables_empty",
                "structurizer: tables есть, но без колонок/строк/row_count",
            ),
        )
    elif total > 0 and good < total:
        soft.append(
            (
                "structurizer_partial_tables",
                f"structurizer: только {good}/{total} таблиц с данными или схемой",
            ),
        )
    return critical, soft


def _evaluate_analyst(result: Dict[str, Any]) -> Tuple[List[Issue], List[Issue]]:
    critical: List[Issue] = []
    soft: List[Issue] = []
    nar = _narrative_text(result)
    fc = _non_empty_finding_count(result)
    if not _has_non_empty_findings(result) and len(nar) < MIN_ANALYST_NARRATIVE_SOFT:
        soft.append(
            (
                "analyst_thin_output",
                "analyst: нет findings с текстом и очень короткий narrative",
            ),
        )
    elif 1 <= fc <= 2 and len(nar) < MIN_ANALYST_NARRATIVE_SOFT:
        soft.append(
            (
                "analyst_thin_narrative_for_findings",
                "analyst: есть findings, но narrative короче порога — проверьте полноту пояснения",
            ),
        )
    return critical, soft


def _evaluate_discovery(result: Dict[str, Any]) -> Tuple[List[Issue], List[Issue]]:
    critical: List[Issue] = []
    soft: List[Issue] = []
    if not _has_discovery_signals(result):
        soft.append(
            ("discovery_empty", "discovery: нет источников/ресурсов и пустой narrative"),
        )
    else:
        src_n = _sources_with_url_count(result)
        if isinstance(result.get("sources"), list) and len(result["sources"]) > 0 and src_n == 0:
            critical.append(
                ("discovery_sources_without_url", "discovery: sources без непустого url"),
            )
        nar = _narrative_text(result)
        if src_n > 0 and len(nar) < MIN_DISCOVERY_NARRATIVE_SOFT:
            soft.append(
                (
                    "discovery_short_narrative",
                    f"discovery: narrative короче {MIN_DISCOVERY_NARRATIVE_SOFT} символов при наличии ссылок",
                ),
            )
    return critical, soft


def _evaluate_research(result: Dict[str, Any]) -> Tuple[List[Issue], List[Issue]]:
    critical: List[Issue] = []
    soft: List[Issue] = []
    if not _has_research_signals(result):
        soft.append(
            ("research_thin", "research: нет URL в sources и пустой narrative"),
        )
    else:
        fetched = _fetched_sources_count(result)
        urls = _sources_with_url_count(result)
        nar = _narrative_text(result)
        if urls > 0 and fetched == 0 and len(nar) < MIN_RESEARCH_NARRATIVE_SOFT:
            soft.append(
                (
                    "research_no_fetched_pages",
                    "research: ни одна страница не помечена fetched при коротком narrative",
                ),
            )
    return critical, soft


def _evaluate_context_filter(result: Dict[str, Any]) -> Tuple[List[Issue], List[Issue]]:
    critical: List[Issue] = []
    soft: List[Issue] = []
    meta = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
    fe = meta.get("filter_expression")
    reason = str(meta.get("reason") or "").strip()
    if fe is None and len(reason) < 8:
        soft.append(
            (
                "context_filter_weak_reason",
                "context_filter: filter_expression=null и слишком короткий reason в metadata",
            ),
        )
    return critical, soft


def _evaluate_validator(result: Dict[str, Any]) -> Tuple[List[Issue], List[Issue]]:
    critical: List[Issue] = []
    soft: List[Issue] = []
    v = _validation_dict(result)
    if v is None:
        critical.append(
            ("validator_missing_validation", "validator: нет поля validation в AgentPayload"),
        )
        return critical, soft
    if "valid" not in v:
        critical.append(
            ("validator_validation_incomplete", "validator: в validation нет ключа valid"),
        )
    issues = v.get("issues") or []
    msg = str(v.get("message") or "").strip()
    if v.get("valid") is False and (not isinstance(issues, list) or len(issues) == 0) and not msg:
        soft.append(
            (
                "validator_invalid_without_detail",
                "validator: valid=false без issues и без message",
            ),
        )
    return critical, soft


def evaluate_step_acceptance(
    *,
    agent_name: str,
    task: Dict[str, Any],
    result: Dict[str, Any],
) -> StepAcceptanceResult:
    """
    Эвристики по AgentPayload (dict после model_dump).

    task: шаг плана ``{"type", "description", ...}`` — overrides: ``acceptance.skip``.
    """
    if not ma_bool("MULTI_AGENT_STEP_ACCEPTANCE_ENABLED", True):
        return StepAcceptanceResult(level="ok")

    agent_name = normalize_step_acceptance_agent_name(agent_name)

    status = str(result.get("status") or "")
    if status == "error":
        return StepAcceptanceResult(level="ok", codes=["skipped_error_status"])

    custom = task.get("acceptance")
    if isinstance(custom, dict) and custom.get("skip") is True:
        return StepAcceptanceResult(level="ok", codes=["skipped_task_acceptance"])

    is_partial = status == "partial"
    critical: List[Issue] = []
    soft: List[Issue] = []

    if agent_name == "reporter":
        c, s = _evaluate_reporter(result)
        critical, soft = c, s
    elif agent_name in ("transform_codex", "widget_codex"):
        c, s = _evaluate_codex(agent_name, result)
        critical, soft = c, s
    elif agent_name == "structurizer":
        c, s = _evaluate_structurizer(result)
        critical, soft = c, s
    elif agent_name == "analyst":
        c, s = _evaluate_analyst(result)
        critical, soft = c, s
    elif agent_name == "discovery":
        c, s = _evaluate_discovery(result)
        critical, soft = c, s
    elif agent_name == "research":
        c, s = _evaluate_research(result)
        critical, soft = c, s
    elif agent_name == "context_filter":
        c, s = _evaluate_context_filter(result)
        critical, soft = c, s
    elif agent_name == "validator":
        c, s = _evaluate_validator(result)
        critical, soft = c, s
    else:
        # planner и прочие: нет per-step критериев (planner не исполняется как шаг execute_step)
        return StepAcceptanceResult(level="ok")

    codes: List[str] = []
    messages: List[str] = []

    if not critical and not soft:
        return StepAcceptanceResult(level="ok")

    for code, msg in critical + soft:
        codes.append(code)
        messages.append(msg)

    if is_partial:
        return StepAcceptanceResult(level="warn", codes=codes, messages=messages)
    if critical:
        return StepAcceptanceResult(level="fail", codes=codes, messages=messages)
    return StepAcceptanceResult(level="warn", codes=codes, messages=messages)


def _init_pipeline_memory_light(context: Dict[str, Any]) -> Dict[str, Any]:
    pm = context.get("pipeline_memory")
    if not isinstance(pm, dict):
        context["pipeline_memory"] = {
            "goal": "",
            "constraints": [],
            "decisions": [],
            "open_questions": [],
            "evidence": [],
        }
        pm = context["pipeline_memory"]
    return pm


def _append_open_question(memory: Dict[str, Any], text: str, *, limit: int = 14) -> None:
    oq = memory.setdefault("open_questions", [])
    if not isinstance(oq, list):
        return
    t = str(text).strip()
    if not t or t in oq:
        return
    oq.append(t)
    if len(oq) > limit:
        del oq[0 : len(oq) - limit]


def record_step_acceptance_in_memory(
    pipeline_context: Dict[str, Any],
    *,
    agent_name: str,
    step_id: Optional[str],
    acceptance: StepAcceptanceResult,
) -> None:
    """Пишет заметки в pipeline_memory для планера на следующих шагах."""
    if acceptance.level == "ok":
        return
    memory = _init_pipeline_memory_light(pipeline_context)
    sid = str(step_id) if step_id is not None else "?"
    prefix = f"[acceptance {acceptance.level}] {agent_name} step={sid}: "
    for msg in acceptance.messages:
        _append_open_question(memory, prefix + msg, limit=14)
    log = pipeline_context.setdefault("_step_acceptance_log", [])
    if isinstance(log, list):
        log.append(
            {
                "agent": agent_name,
                "step_id": sid,
                **acceptance.to_trace_dict(),
            }
        )
