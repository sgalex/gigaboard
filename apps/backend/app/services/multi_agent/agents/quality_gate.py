"""
Quality Gate Agent (ValidatorAgent V2) — Pipeline Result Validation
Проверяет соответствие результатов работы агентов запросу пользователя.

V2: Заменяет CriticAgent. Возвращает AgentPayload(validation=ValidationResult(...)).
    Gate-keeper: valid → pass, suggested_replan → replan (макс 3 итерации).
    См. docs/MULTI_AGENT_V2_CONCEPT.md

Note: Файл назван quality_gate.py чтобы не конфликтовать с validator.py,
      который выполняет code-level валидацию (синтаксис, безопасность).
      Agent name = "validator" (V2).
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from .base import BaseAgent
from ..message_bus import AgentMessageBus
from ..schemas.agent_payload import (
    Finding,
    PlanStep,
    SuggestedReplan,
    ValidationResult,
)
from app.services.gigachat_service import GigaChatService

logger = logging.getLogger(__name__)


# ── keywords for expected outcome detection ──────────────────────────
_CODE_KW = ["код", "напиши код", "скрипт", "python", "sql"]
_VIZ_KW = ["график", "визуализ", "диаграмм", "виджет"]
_TRANSFORM_KW = [
    "трансформируй", "преобразуй", "отфильтруй",
    "сгруппируй", "добавь столбец",
]
_DATA_KW = ["данные", "загрузи", "получи данные", "скачай"]


QUALITY_GATE_SYSTEM_PROMPT = """
Ты — ValidatorAgent (Quality Gate) в системе GigaBoard Multi-Agent V2.

РОЛЬ: Проверка результатов работы агентов на соответствие запросу пользователя.

ЧТО ОЦЕНИВАЕШЬ:
1. Соответствие результата исходному запросу (intent matching).
2. Полнота выполнения (все аспекты запроса покрыты).
3. Наличие требуемых артефактов (код, данные, визуализация).
4. Качество и корректность результата.

ФОРМАТ ВЫВОДА (строго JSON):
{
  "valid": true|false,
  "confidence": 0.0-1.0,
  "message": "краткое пояснение",
  "issues": [
    {"severity": "critical|warning", "message": "описание проблемы"}
  ],
  "recommendations": [
    {"action": "описание", "agent": "имя_агента"}
  ],
  "suggested_replan": null | {
    "reason": "причина",
    "additional_steps": [
      {"agent": "имя_агента", "description": "что сделать"}
    ]
  }
}

ПРАВИЛА:
- Будь СТРОГ к code_generation / transformation: код ОБЯЗАН быть.
- Будь гибок к research: текстовый ответ приемлем.
- Если итерация >= max, НЕ давай suggested_replan.
- Рекомендации должны быть actionable.
"""


class QualityGateAgent(BaseAgent):
    """
    Quality Gate (ValidatorAgent V2) — проверяет результат пайплайна.

    1. Определяет expected outcome по запросу.
    2. Быстрая heuristic-проверка (уверенность ≥ 0.9 → без LLM).
    3. LLM-валидация через GigaChat при неоднозначности.
    4. Возвращает ``AgentPayload(validation=ValidationResult(...))``.

    Gate decisions:
      valid=True  → Orchestrator завершает пайплайн.
      valid=False + suggested_replan → Orchestrator делает replan (до 3 раз).
      valid=False без replan → Orchestrator завершает с предупреждением.
    """

    def __init__(
        self,
        message_bus: AgentMessageBus,
        gigachat_service: GigaChatService,
        system_prompt: Optional[str] = None,
        executor = None,
    ):
        super().__init__(
            agent_name="validator",
            message_bus=message_bus,
            system_prompt=system_prompt,
        )
        self.gigachat = gigachat_service
        self.executor = executor  # PythonExecutor для проверки кода

    def _get_default_system_prompt(self) -> str:
        return QUALITY_GATE_SYSTEM_PROMPT

    # ── main entry ───────────────────────────────────────────────────
    async def process_task(
        self,
        task: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ):
        """
        Валидирует результаты пайплайна.

        Task fields:
          original_request — запрос пользователя
          aggregated_result | (context.agent_results) — данные для проверки
          expected_outcome  — (опционально) тип ожидаемого результата
          iteration         — текущая итерация (default 1)
          max_iterations    — лимит (default 3)

        V2: Возвращает AgentPayload(validation=ValidationResult(...)).
        """
        try:
            original_request = (
                task.get("original_request")
                or task.get("user_request", "")
            )
            iteration = task.get("iteration", 1)
            max_iterations = task.get("max_iterations", 3)

            # Данные для проверки (поддерживаем оба варианта имени поля)
            aggregated: Dict[str, Any] = (
                task.get("aggregated_result")
                or task.get("aggregated_payload")
                or {}
            )
            if not aggregated:
                # Изменение #2: agent_results — list, конвертируем в dict для heuristic
                agent_results = (context or {}).get("agent_results", [])
                if agent_results:
                    aggregated = {
                        r.get("agent", f"agent_{i}"): r
                        for i, r in enumerate(agent_results)
                        if isinstance(r, dict)
                    }

            expected = (
                task.get("expected_outcome")
                or self._detect_outcome(original_request)
            )

            self.logger.info(
                f"🔍 QualityGate: expected={expected}, "
                f"iter={iteration}/{max_iterations}, "
                f"agents={list(aggregated.keys())}"
            )

            # ── Heuristic (fast) ─────────────────────────────────────
            h = self._heuristic(expected, aggregated, original_request)
            
            # ── V2: Code execution validation ───────────────────────
            # Если ожидается code_generation и есть executor - выполняем код
            execution_result = None
            if (expected in ("code_generation", "transformation") 
                and self.executor 
                and context
                and context.get("input_data")):
                execution_result = await self._execute_code_validation(
                    aggregated, context, original_request
                )
                # Если execution failed - возвращаем error с suggested_replan
                if execution_result and not execution_result.get("success"):
                    vr = self._create_execution_error_result(
                        execution_result, iteration, max_iterations
                    )
                    self.logger.warning(
                        f"❌ FAIL (execution error): {execution_result.get('error')}"
                    )
                    return self._success_payload(validation=vr)

            if h.get("confidence", 0) >= 0.9:
                vr = self._to_validation_result(h, iteration, max_iterations)
                tag = "✅ PASS" if vr.valid else "❌ FAIL"
                self.logger.info(
                    f"{tag} (heuristic, conf={vr.confidence})"
                )
                return self._success_payload(validation=vr)

            # ── LLM (deep) ───────────────────────────────────────────
            try:
                llm_raw = await self._llm_validate(
                    original_request,
                    expected,
                    aggregated,
                    iteration,
                    max_iterations,
                )
                vr = self._to_validation_result(
                    llm_raw, iteration, max_iterations
                )
            except Exception as e:
                self.logger.warning(
                    f"LLM validation failed, fallback heuristic: {e}"
                )
                vr = self._to_validation_result(h, iteration, max_iterations)

            tag = "✅ PASS" if vr.valid else "❌ FAIL"
            self.logger.info(f"{tag} (conf={vr.confidence})")
            return self._success_payload(validation=vr)

        except Exception as e:
            self.logger.error(f"QualityGateAgent error: {e}", exc_info=True)
            return self._error_payload(str(e))

    # ═════════════════════════════════════════════════════════════════
    #  Outcome detection
    # ═════════════════════════════════════════════════════════════════
    @staticmethod
    def _detect_outcome(msg: str) -> str:
        low = msg.lower()
        if any(k in low for k in _CODE_KW):
            return "code_generation"
        if any(k in low for k in _VIZ_KW):
            return "visualization"
        if any(k in low for k in _TRANSFORM_KW):
            return "transformation"
        if any(k in low for k in _DATA_KW):
            return "data_extraction"
        return "research"

    # ═════════════════════════════════════════════════════════════════
    #  Heuristic validation
    # ═════════════════════════════════════════════════════════════════
    def _heuristic(
        self,
        expected: str,
        aggregated: Dict[str, Any],
        original_request: str,
    ) -> Dict[str, Any]:
        """Fast rule-based validation without LLM."""
        txt = json.dumps(aggregated, ensure_ascii=False, default=str)

        # ── Check for agent-level errors ─────────────────────────────
        for agent_name, res in aggregated.items():
            if not isinstance(res, dict):
                continue
            
            # execution error (code ran and crashed)
            er = res.get("execution_result")
            if isinstance(er, dict) and er.get("execution_success") is False:
                return {
                    "valid": False,
                    "confidence": 1.0,
                    "message": f"Code execution error: {er.get('execution_error', '')}",
                    "issues": [
                        {
                            "severity": "critical",
                            "message": f"Execution error: {er.get('execution_error', '')}",
                        }
                    ],
                }
            
            # V2 payload with status=error
            if res.get("status") == "error":
                return {
                    "valid": False,
                    "confidence": 0.95,
                    "message": f"Agent {agent_name} error: {res.get('error', '')}",
                    "issues": [
                        {
                            "severity": "critical",
                            "message": res.get("error", "unknown"),
                        }
                    ],
                }
            
            # Check for empty/invalid results from critical agents
            # Analyst должен вернуть findings
            if agent_name == "analyst":
                findings = res.get("findings", [])
                if not findings or len(findings) == 0:
                    return {
                        "valid": False,
                        "confidence": 0.9,
                        "message": "Analyst returned no findings",
                        "issues": [
                            {
                                "severity": "critical",
                                "message": "Analyst failed to analyze data - no insights generated",
                            }
                        ],
                        "suggested_replan": {
                            "reason": "Analyst returned empty findings - need to retry analysis",
                            "additional_steps": [
                                {
                                    "agent": "analyst",
                                    "description": "Re-analyze data with explicit instructions to generate findings",
                                }
                            ],
                        },
                    }
                
                # Check if all findings have empty text
                empty_findings = sum(1 for f in findings if not f.get("text", "").strip())
                if empty_findings == len(findings):
                    return {
                        "valid": False,
                        "confidence": 0.9,
                        "message": f"Analyst returned {len(findings)} findings with empty text",
                        "issues": [
                            {
                                "severity": "critical",
                                "message": "All findings have empty descriptions",
                            }
                        ],
                        "suggested_replan": {
                            "reason": "Analyst findings are empty - LLM parsing failed",
                            "additional_steps": [
                                {
                                    "agent": "analyst",
                                    "description": "Retry analysis with stricter output format validation",
                                }
                            ],
                        },
                    }
            
            # Codex должен вернуть code_blocks с кодом
            if agent_name == "transform_codex" and expected in ["code_generation", "transformation"]:
                code_blocks = res.get("code_blocks", [])
                if code_blocks:
                    # Проверяем что есть хотя бы один блок с непустым кодом
                    has_code = any(
                        cb.get("code", "").strip() 
                        for cb in code_blocks 
                        if isinstance(cb, dict)
                    )
                    if not has_code:
                        return {
                            "valid": False,
                            "confidence": 0.9,
                            "message": "Codex returned empty code blocks",
                            "issues": [
                                {
                                    "severity": "critical",
                                    "message": "Code generation failed - empty code",
                                }
                            ],
                            "suggested_replan": {
                                "reason": "Codex returned empty code - need to retry generation",
                                "additional_steps": [
                                    {
                                        "agent": "transform_codex",
                                        "description": "Regenerate code with explicit requirements",
                                    }
                                ],
                            },
                        }

        # ── outcome-specific checks ─────────────────────────────────
        if expected == "code_generation":
            # Check if any code_block has syntax_valid=False or empty code
            has_invalid = self._has_invalid_code_blocks(aggregated)
            if has_invalid:
                return {
                    "valid": False, "confidence": 0.95,
                    "message": f"Code invalid: {has_invalid}",
                    "issues": [{"severity": "critical", "message": has_invalid}],
                    "suggested_replan": {
                        "reason": f"Code generation failed: {has_invalid}",
                        "additional_steps": [{
                            "agent": "transform_codex",
                            "description": "Regenerate code — previous attempt returned invalid/empty code",
                        }],
                    },
                }
            # Проверяем наличие реального кода (не просто ключа "code_blocks")
            has_real_code = self._has_nonempty_code(aggregated)
            if has_real_code:
                return {"valid": True, "confidence": 0.95, "message": "Valid code found"}
            if bool(re.search(r'```(python|sql|javascript)', txt)):
                return {"valid": True, "confidence": 0.9, "message": "Code block found in text"}
            return {
                "valid": False, "confidence": 0.85,
                "message": "No code found",
                "issues": [{"severity": "critical", "message": "Missing code"}],
            }

        if expected == "visualization":
            if "widget_code" in txt or "widget_type" in txt:
                return {"valid": True, "confidence": 0.9, "message": "Widget found"}
            if "code_blocks" in txt and "html" in txt.lower():
                return {"valid": True, "confidence": 0.85, "message": "HTML code found"}
            return {
                "valid": False, "confidence": 0.8,
                "message": "No widget",
                "issues": [{"severity": "critical", "message": "Missing visualization"}],
            }

        if expected == "transformation":
            # Check if any code_block has syntax_valid=False or empty code
            has_invalid = self._has_invalid_code_blocks(aggregated)
            if has_invalid:
                return {
                    "valid": False, "confidence": 0.95,
                    "message": f"Code invalid: {has_invalid}",
                    "issues": [{"severity": "critical", "message": has_invalid}],
                    "suggested_replan": {
                        "reason": f"Transformation code generation failed: {has_invalid}",
                        "additional_steps": [{
                            "agent": "transform_codex",
                            "description": "Regenerate transformation code — previous attempt failed",
                        }],
                    },
                }
            # Проверяем наличие реального кода
            has_real_code = self._has_nonempty_code(aggregated)
            if has_real_code and bool(re.search(r'df_[a-z_][a-z0-9_]*', txt)):
                return {"valid": True, "confidence": 0.95, "message": "Transformation code with df_ variable found"}
            if has_real_code:
                return {"valid": True, "confidence": 0.85, "message": "Code present"}
            if "transformation_code" in txt:
                return {"valid": True, "confidence": 0.8, "message": "Transformation code key found"}
            return {
                "valid": False, "confidence": 0.85,
                "message": "No transformation code",
                "issues": [{"severity": "critical", "message": "Missing pandas code"}],
            }

        if expected == "data_extraction":
            if "tables" in txt or "sources" in txt:
                return {"valid": True, "confidence": 0.9, "message": "Data found"}
            return {
                "valid": False, "confidence": 0.7,
                "message": "No data",
                "issues": [{"severity": "warning", "message": "Missing structured data"}],
            }

        # research — almost any textual answer is OK
        has_content = len(txt) > 100
        return {
            "valid": has_content,
            "confidence": 0.85 if has_content else 0.5,
            "message": "Content present" if has_content else "Empty result",
        }

    # ═════════════════════════════════════════════════════════════════
    #  LLM validation
    # ═════════════════════════════════════════════════════════════════
    async def _llm_validate(
        self,
        original_request: str,
        expected: str,
        aggregated: Dict[str, Any],
        iteration: int,
        max_iterations: int,
    ) -> Dict[str, Any]:
        summary = self._summarize(aggregated)
        no_replan = (
            " НЕ предлагай suggested_replan."
            if iteration >= max_iterations
            else ""
        )

        prompt = (
            f"Запрос пользователя: {original_request}\n"
            f"Ожидаемый тип результата: {expected}\n"
            f"Итерация: {iteration}/{max_iterations}.{no_replan}\n\n"
            f"Результаты агентов:\n{summary}\n\n"
            "Верни JSON валидации."
        )
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]
        response = await self.gigachat.chat_completion(
            messages=messages, temperature=0.3, max_tokens=1500
        )
        return self._parse_json(response)

    # ═════════════════════════════════════════════════════════════════
    #  Helpers
    # ═════════════════════════════════════════════════════════════════
    @staticmethod
    def _has_invalid_code_blocks(aggregated: Dict[str, Any]) -> Optional[str]:
        """
        Проверяет code_blocks во всех результатах агентов.
        Возвращает описание ошибки если есть невалидный блок, иначе None.
        
        Поддерживает два формата aggregated:
        - flat: {"code_blocks": [...], "agent": "...", ...} (merged AgentPayload)
        - keyed: {"agent_name": {"code_blocks": [...], ...}, ...} (dict of agents)
        """
        # Собираем все code_blocks из обоих форматов
        all_code_blocks: List[Any] = []
        
        # Flat format: aggregated сам содержит code_blocks
        if "code_blocks" in aggregated and isinstance(aggregated["code_blocks"], list):
            all_code_blocks.extend(aggregated["code_blocks"])
        
        # Keyed format: перебираем значения-dict
        for _agent, result in aggregated.items():
            if not isinstance(result, dict):
                continue
            for cb in result.get("code_blocks", []):
                all_code_blocks.append(cb)
        
        for cb in all_code_blocks:
            if isinstance(cb, dict):
                # Невалидный синтаксис
                if cb.get("syntax_valid") is False:
                    return cb.get("description", "") or "syntax_valid=False"
                # Пустой код — тоже ошибка
                if not cb.get("code", "").strip():
                    return "empty code block"
        return None

    @staticmethod
    def _has_nonempty_code(aggregated: Dict[str, Any]) -> bool:
        """
        Проверяет наличие хотя бы одного code_block с непустым кодом.
        Поддерживает flat и keyed форматы aggregated.
        """
        # Flat format
        for cb in aggregated.get("code_blocks", []):
            if isinstance(cb, dict) and cb.get("code", "").strip():
                return True
        # Keyed format
        for _agent, result in aggregated.items():
            if not isinstance(result, dict):
                continue
            for cb in result.get("code_blocks", []):
                if isinstance(cb, dict) and cb.get("code", "").strip():
                    return True
        return False

    def _summarize(self, aggregated: Dict[str, Any]) -> str:
        """Краткая сводка результатов для LLM."""
        parts: List[str] = []
        for agent, result in aggregated.items():
            if not isinstance(result, dict):
                parts.append(f"{agent}: {str(result)[:200]}")
                continue

            s: Dict[str, Any] = {
                "agent": agent,
                "status": result.get("status", "?"),
            }

            # V2 sections
            nar = result.get("narrative")
            if isinstance(nar, dict) and nar.get("text"):
                s["narrative"] = nar["text"][:300]
            elif isinstance(nar, str) and nar:
                s["narrative"] = nar[:300]

            if result.get("findings"):
                s["findings_count"] = len(result["findings"])
            if result.get("code_blocks"):
                s["code_blocks_count"] = len(result["code_blocks"])
                # Show first code block preview
                first_cb = result["code_blocks"][0]
                if isinstance(first_cb, dict):
                    s["code_preview"] = first_cb.get("code", "")[:300]
            if result.get("tables"):
                s["tables_count"] = len(result["tables"])

            # V1 compat
            if result.get("transformation_code"):
                s["transformation_code"] = result["transformation_code"]
            if result.get("widget_type"):
                s["widget_type"] = result["widget_type"]

            parts.append(json.dumps(s, ensure_ascii=False, indent=2))

        return "\n\n".join(parts)

    @staticmethod
    def _parse_json(response: str) -> Dict[str, Any]:
        m = re.search(r'\{[\s\S]*\}', response)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
        return {
            "valid": True,
            "confidence": 0.5,
            "message": "Parse error — default pass",
        }

    def _to_validation_result(
        self,
        raw: Dict[str, Any],
        iteration: int,
        max_iterations: int,
    ) -> ValidationResult:
        """Convert raw dict → ValidationResult Pydantic model."""
        # ── issues ───────────────────────────────────────────────────
        issues: List[Finding] = []
        for iss in raw.get("issues", []):
            if isinstance(iss, dict):
                issues.append(
                    Finding(
                        type="validation_issue",
                        text=iss.get("message", ""),
                        severity=iss.get("severity", "warning"),  # type: ignore[arg-type]
                    )
                )

        # ── recommendations ──────────────────────────────────────────
        recommendations: List[Finding] = []
        for rec in raw.get("recommendations", []):
            if isinstance(rec, dict):
                recommendations.append(
                    Finding(
                        type="recommendation",
                        text=rec.get("description", rec.get("action", "")),
                        action=rec.get("agent"),
                    )
                )

        # ── suggested_replan (blocked on last iteration) ─────────────
        suggested_replan: Optional[SuggestedReplan] = None
        sr = raw.get("suggested_replan")
        if sr and isinstance(sr, dict) and iteration < max_iterations:
            steps: List[PlanStep] = []
            for i, st in enumerate(sr.get("additional_steps", []), 1):
                if isinstance(st, dict):
                    steps.append(
                        PlanStep(
                            step_id=str(i),
                            agent=st.get("agent", "analyst"),
                            task={
                                "description": st.get(
                                    "description", st.get("task", "")
                                )
                            },
                        )
                    )
            if steps:
                suggested_replan = SuggestedReplan(
                    reason=sr.get("reason", "Validation failed"),
                    additional_steps=steps,
                )

        return ValidationResult(
            valid=raw.get("valid", True),
            confidence=raw.get("confidence", 0.5),
            message=raw.get("message"),
            issues=issues,
            recommendations=recommendations,
            suggested_replan=suggested_replan,
        )
    # ═════════════════════════════════════════════════════════════════
    #  V2: Code Execution Validation
    # ═════════════════════════════════════════════════════════════════
    async def _execute_code_validation(
        self,
        aggregated: Dict[str, Any],
        context: Dict[str, Any],
        original_request: str,
    ) -> Dict[str, Any]:
        """
        Выполняет сгенерированный код на реальных данных.
        
        Если multi-step план породил несколько code_blocks, конкатенирует
        их в единый скрипт (каждый шаг — дополнение предыдущего).
        
        Returns:
            {
                "success": True/False,
                "error": str (если failed),
                "error_type": "syntax|runtime|....",
                "output": Any (если success)
            }
        """
        try:
            # Извлекаем код из aggregated results
            code_blocks = aggregated.get("code_blocks", [])
            if not code_blocks:
                self.logger.debug("⚠️ No code_blocks found for execution validation")
                return {"success": True, "message": "No code to validate"}
            
            # Multi-step code composition:
            # Если в плане несколько шагов codex, каждый генерирует свой code_block.
            # Конкатенируем все блоки в единый скрипт, чтобы шаг N
            # видел результаты шагов 1..N-1 (напр. очистку null → агрегацию).
            non_empty_blocks = []
            for cb in code_blocks:
                block_code = cb.get("code", "") if isinstance(cb, dict) else cb
                if block_code and block_code.strip():
                    non_empty_blocks.append(block_code.strip())
            
            if not non_empty_blocks:
                return {"success": True, "message": "Empty code"}
            
            # Дедупликация: если codex и reporter отдали один и тот же блок,
            # не нужно выполнять его дважды.
            seen_codes: set[str] = set()
            unique_blocks: list[str] = []
            for blk in non_empty_blocks:
                if blk not in seen_codes:
                    seen_codes.add(blk)
                    unique_blocks.append(blk)
            if len(unique_blocks) < len(non_empty_blocks):
                self.logger.debug(
                    f"🧹 QualityGate: Deduplicated {len(non_empty_blocks)} → {len(unique_blocks)} code blocks"
                )
            non_empty_blocks = unique_blocks

            if len(non_empty_blocks) > 1:
                # Конкатенируем с разделителем-комментарием для отладки
                code = "\n\n# --- multi-step composition ---\n\n".join(non_empty_blocks)
                self.logger.info(
                    f"🔗 QualityGate: Composed {len(non_empty_blocks)} code blocks "
                    f"into single script ({len(code)} chars)"
                )
            else:
                code = non_empty_blocks[0]
            
            # Извлекаем input_data из context
            input_data = context.get("input_data", {})
            if not input_data:
                self.logger.debug("⚠️ No input_data in context for execution")
                return {"success": True, "message": "No input data to validate against"}
            
            self.logger.info(f"🔧 ValidatorAgent: Executing code ({len(code)} chars) on {len(input_data)} inputs...")
            
            # Выполняем код через PythonExecutor
            # Изменение #6: auth_token убран (агенты внутри backend)
            result = await self.executor.execute_transformation(
                code=code,
                input_data=input_data,
                user_id=context.get("user_id"),
            )
            
            if not result.success:
                error_msg = result.error or "Unknown execution error"
                self.logger.warning(f"❌ Code execution failed: {error_msg}")

                # Обогащаем NameError контекстом из existing_code,
                # чтобы при replan codex получил конкретную инструкцию.
                existing_code = (context or {}).get("existing_code", "")
                if existing_code and re.search(r"name 'df_\w+' is not defined", error_msg):
                    import re as _re
                    m = _re.search(r"name '(df_\w+)' is not defined", error_msg)
                    var_name = m.group(1) if m else "df_xxx"
                    error_msg = (
                        f"{error_msg}\n\n"
                        f"⚠️ ПРИЧИНА: Переменная '{var_name}' определена в ТЕКУЩЕМ КОДЕ "
                        f"(existing_code), но ты НЕ включил её определение в свой ответ.\n"
                        f"🔧 РЕШЕНИЕ: Сгенерируй ПОЛНЫЙ САМОДОСТАТОЧНЫЙ код, который "
                        f"включает ВСЮ логику из ТЕКУЩЕГО КОДА (определение '{var_name}' и др.) "
                        f"ПЛЮС новый запрос. Код должен выполняться с нуля без внешних переменных."
                    )
                    self.logger.info(
                        f"📎 QualityGate: Enriched NameError with existing_code context for '{var_name}'"
                    )

                return {
                    "success": False,
                    "error": error_msg,
                    "error_type": "runtime",
                    "failed_code": code,  # Сохраняем для контекста replan
                }
            
            self.logger.info(f"✅ Code execution succeeded: {len(result.result_dfs)} output tables")
            return {
                "success": True,
                "output": result.result_dfs,
                "execution_time_ms": result.execution_time_ms,
            }
            
        except Exception as e:
            self.logger.error(f"❌ Execution validation error: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "error_type": "validation_error",
            }

    def _create_execution_error_result(
        self,
        execution_result: Dict[str, Any],
        iteration: int,
        max_iterations: int,
    ) -> ValidationResult:
        """Создает ValidationResult для ошибки выполнения кода с suggested_replan."""
        error_msg = execution_result.get("error", "Unknown execution error")
        error_type = execution_result.get("error_type", "runtime")
        
        # Формируем suggested_replan только если не достигли max_iterations
        suggested_replan = None
        if iteration < max_iterations:
            suggested_replan = SuggestedReplan(
                reason=f"Code execution failed: {error_msg}",
                additional_steps=[
                    PlanStep(
                        step_id="fix-1",
                        agent="transform_codex",
                        task={
                            "description": f"Fix code execution error: {error_msg}",
                            "purpose": "transformation",
                            "error_details": {
                                "error": error_msg,
                                "error_type": error_type,
                            }
                        }
                    )
                ]
            )
        
        return ValidationResult(
            valid=False,
            confidence=1.0,  # Мы уверены что код не работает
            message=f"Code execution failed ({error_type}): {error_msg}",
            issues=[
                Finding(
                    type="validation_issue",
                    text=f"Generated code fails on execution: {error_msg}",
                    severity="critical",
                    confidence=1.0,
                )
            ],
            recommendations=[],
            suggested_replan=suggested_replan,
        )