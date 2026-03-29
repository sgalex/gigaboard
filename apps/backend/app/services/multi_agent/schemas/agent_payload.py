"""
AgentPayload — универсальный формат данных для всех агентов Multi-Agent V2.

Каждый core-агент возвращает AgentPayload. Satellite-контроллеры читают
нужные секции напрямую. Orchestrator передаёт agent_results (хронологический list)
без маппинга — каждый агент сам берёт нужные секции.

См. docs/MULTI_AGENT_V2_CONCEPT.md для полной спецификации.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


# ============================================================
# Вложенные модели (leaf-first ordering для forward references)
# ============================================================


class Narrative(BaseModel):
    """Текстовый ответ для пользователя."""

    text: str = Field(..., description="Текст ответа")
    format: Literal["markdown", "plain", "html"] = Field(
        default="markdown", description="Формат текста"
    )


class Column(BaseModel):
    """Описание колонки таблицы."""

    name: str = Field(..., description="Имя колонки")
    type: str = Field(
        default="string",
        description='Тип данных: "string" | "int" | "float" | "date" | "bool"',
    )


class PayloadContentTable(BaseModel):
    """Единый формат структурированных данных в AgentPayload.

    Unified format:
      columns: [{name: str, type: str}, ...]
      rows: [{col_name: value, ...}, ...]
    """

    id: str = Field(
        default_factory=lambda: str(uuid4()), description="UUID таблицы"
    )
    name: str = Field(..., description='Семантическое имя, e.g. "sales_by_region"')
    columns: list[Column] = Field(
        default_factory=list, description="Описания колонок"
    )
    rows: list[dict[str, Any]] = Field(default_factory=list, description="Строки данных [{col: val}, ...]")
    row_count: int = Field(default=0, description="Общее количество строк")
    column_count: int = Field(default=0, description="Количество колонок")
    preview_row_count: int = Field(
        default=0, description="Строк в preview (≤100)"
    )

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------

    def to_content_table_dict(self) -> dict[str, Any]:
        """Конвертировать в формат ``app.schemas.content_node.ContentTable``."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PayloadContentTable":
        """Создать из ContentTable dict.
        
        Формат:
          columns: [{name: str, type: str}, ...]
          rows: [{col_name: value, ...}, ...]
        """
        columns = [
            Column(name=col.get("name", ""), type=col.get("type", "string"))
            for col in data.get("columns", [])
        ]

        rows: list[dict[str, Any]] = data.get("rows", [])

        row_count = data.get("row_count", len(rows))
        column_count = data.get("column_count", len(columns))
        preview_row_count = data.get("preview_row_count", min(row_count, 100))

        return cls(
            id=data.get("id", str(uuid4())),
            name=data.get("name", "без названия"),
            columns=columns,
            rows=rows,
            row_count=row_count,
            column_count=column_count,
            preview_row_count=preview_row_count,
        )


class CodeBlock(BaseModel):
    """Блок сгенерированного кода."""

    code: str = Field(..., description="Исходный код")
    language: Literal["python", "html", "sql", "javascript"] = Field(
        ..., description="Язык программирования"
    )
    purpose: Literal["transformation", "widget", "analysis", "utility"] = Field(
        ..., description="Назначение кода"
    )
    variable_name: Optional[str] = Field(
        default=None,
        description='Имя результирующей переменной, e.g. "df_sales_filtered"',
    )
    syntax_valid: Optional[bool] = Field(
        default=None, description="Результат syntax check от TransformCodexAgent/WidgetCodexAgent"
    )
    warnings: list[str] = Field(
        default_factory=list, description="Предупреждения"
    )
    description: Optional[str] = Field(
        default=None, description="Имя виджета или описание кода"
    )


SourceResourceKind = Literal[
    "html_page",
    "image",
    "video",
    "audio",
    "json",
    "xml",
    "text",
    "pdf",
    "document",
    "feed",
    "other",
    "unknown",
]


class Source(BaseModel):
    """Источник информации (URL, API, файл)."""

    url: str = Field(..., description="URL источника")
    title: Optional[str] = Field(default=None, description="Заголовок")
    snippet: Optional[str] = Field(
        default=None, description="Краткий фрагмент текста"
    )
    content: Optional[str] = Field(
        default=None, description="Полный текст (после fetch)"
    )
    source_type: Literal["web", "news", "api", "database", "file"] = Field(
        default="web", description="Тип источника (канал: web/news/…)"
    )
    # Семантика ресурса по ответу HTTP / эвристике URL (для downstream-агентов)
    mime_type: Optional[str] = Field(
        default=None,
        description="Нормализованный MIME из Content-Type (без charset)",
    )
    resource_kind: SourceResourceKind = Field(
        default="unknown",
        description="Страница HTML / изображение / видео / JSON / …",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Доп. метаданные: embedded_media, binary_body, …",
    )
    status_code: Optional[int] = Field(
        default=None, description="HTTP status code"
    )
    fetched: bool = Field(
        default=False, description="True если content загружен"
    )
    content_size: Optional[int] = Field(
        default=None, description="Размер контента в байтах"
    )
    crawl_depth: Optional[int] = Field(
        default=None,
        description="Глубина волны обхода: 0 — корень (Discovery/явные URL), далее +1 за уровень",
    )


DiscoveredResourceOrigin = Literal["page", "embedded", "link"]


class DiscoveredResource(BaseModel):
    """Ресурс, найденный при исследовании (страница, вложенное медиа, ссылка).

    Отделён от ``Source``: это каталог URL с метаданными для downstream-агентов,
    даже если полный контент не входит в ``Source.content``.
    """

    url: str = Field(..., description="URL ресурса")
    resource_kind: SourceResourceKind = Field(
        default="unknown",
        description="Тип ресурса (html_page, image, video, …)",
    )
    mime_type: Optional[str] = Field(
        default=None,
        description="MIME, если известен",
    )
    parent_url: Optional[str] = Field(
        default=None,
        description="Страница-родитель для вложенных ссылок (embedded)",
    )
    origin: DiscoveredResourceOrigin = Field(
        default="embedded",
        description="page — загруженный документ; embedded — img/video/…; link — гиперссылка",
    )
    tag: Optional[str] = Field(
        default=None,
        description="img, video, a, …",
    )
    title: Optional[str] = Field(
        default=None,
        description="Заголовок страницы или anchor для ссылок",
    )


class Finding(BaseModel):
    """Вывод, рекомендация или проблема."""

    type: Literal[
        "insight",
        "recommendation",
        "data_quality_issue",
        "validation_issue",
        "warning",
    ] = Field(..., description="Тип находки")
    text: str = Field(..., description="Описание")
    severity: Literal["critical", "high", "medium", "low", "info"] = Field(
        default="medium", description="Важность"
    )
    confidence: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Уверенность 0.0-1.0"
    )
    refs: list[str] = Field(
        default_factory=list,
        description="Ссылки на колонки, таблицы, шаги",
    )
    action: Optional[str] = Field(
        default=None, description="Рекомендуемое действие"
    )
    metadata: Optional[dict[str, Any]] = Field(
        default=None, description="Дополнительные данные (type, relevance, prompt и т.д.)"
    )


class PlanStep(BaseModel):
    """Шаг плана выполнения."""

    step_id: str = Field(..., description='Идентификатор шага: "1", "2", ...')
    agent: str = Field(
        ...,
        description='Имя агента: "discovery" | "research" | "transform_codex" | ...',
    )
    task: dict[str, Any] = Field(
        default_factory=dict, description="Задача для агента"
    )
    depends_on: list[str] = Field(
        default_factory=list, description="Зависимости от step_id"
    )
    estimated_time: Optional[str] = Field(
        default=None, description='Оценка времени, e.g. "3s"'
    )


class SuggestedReplan(BaseModel):
    """Рекомендация по перепланированию от ValidatorAgent."""

    reason: str = Field(..., description="Причина перепланирования")
    additional_steps: list[PlanStep] = Field(
        default_factory=list, description="Дополнительные шаги"
    )


class ToolRequest(BaseModel):
    """Запрос на вызов инструмента от агента."""

    request_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Уникальный id запроса инструмента",
    )
    tool_name: str = Field(..., description="Имя инструмента")
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Аргументы инструмента",
    )
    reason: Optional[str] = Field(
        default=None,
        description="Короткое обоснование вызова инструмента",
    )


class ToolResult(BaseModel):
    """Результат вызова инструмента."""

    request_id: str = Field(..., description="request_id исходного ToolRequest")
    tool_name: str = Field(..., description="Имя инструмента")
    success: bool = Field(..., description="Успешно ли выполнен инструмент")
    data: Optional[dict[str, Any]] = Field(
        default=None,
        description="Полезные данные инструмента",
    )
    error: Optional[str] = Field(
        default=None,
        description="Текст ошибки при success=false",
    )


class ValidationResult(BaseModel):
    """Результат валидации от ValidatorAgent."""

    valid: bool = Field(..., description="Результат соответствует запросу")
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Уверенность 0.0-1.0"
    )
    message: Optional[str] = Field(
        default=None, description="Пояснение"
    )
    issues: list[Finding] = Field(
        default_factory=list, description='Проблемы (type="validation_issue")'
    )
    recommendations: list[Finding] = Field(
        default_factory=list, description='Рекомендации (type="recommendation")'
    )
    suggested_replan: Optional[SuggestedReplan] = Field(
        default=None, description="Рекомендация перепланирования"
    )


class Plan(BaseModel):
    """План выполнения от PlannerAgent."""

    plan_id: str = Field(
        default_factory=lambda: str(uuid4()), description="UUID плана"
    )
    user_request: str = Field(..., description="Исходный запрос пользователя")
    steps: list[PlanStep] = Field(
        default_factory=list, description="Шаги плана"
    )
    estimated_total_time: Optional[str] = Field(
        default=None, description='Общее время, e.g. "23s"'
    )


# ============================================================
# AgentPayload — основная модель
# ============================================================


class AgentPayload(BaseModel):
    """Универсальный формат данных для всех core-агентов Multi-Agent V2.

    Каждый агент заполняет релевантные секции, оставляя остальные пустыми.
    Satellite-контроллеры читают нужные секции напрямую.
    Orchestrator передаёт ``agent_results`` (хронологический list) без маппинга.

    См. docs/MULTI_AGENT_V2_CONCEPT.md
    """

    # === ENVELOPE (обязательные) ===
    status: Literal["success", "error", "partial"] = Field(
        ..., description="Результат выполнения"
    )
    agent: str = Field(..., description="Имя агента-отправителя")
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="ISO 8601 timestamp",
    )

    # === NARRATIVE (текстовый ответ) ===
    narrative: Optional[Narrative] = Field(
        default=None, description="Текстовый ответ для пользователя"
    )

    # === DATA (структурированные данные) ===
    tables: list[PayloadContentTable] = Field(
        default_factory=list, description="Структурированные данные (ContentTable)"
    )

    # === CODE (сгенерированный код) ===
    code_blocks: list[CodeBlock] = Field(
        default_factory=list, description="Блоки сгенерированного кода"
    )

    # === SOURCES (источники информации) ===
    sources: list[Source] = Field(
        default_factory=list, description="Источники (URL, API, файлы)"
    )

    # === DISCOVERED RESOURCES (каталог URL с метаданными, в т.ч. медиа со страниц) ===
    discovered_resources: list[DiscoveredResource] = Field(
        default_factory=list,
        description="Найденные ресурсы (ссылки + kind/mime/parent) для контекста агентов",
    )

    # === FINDINGS (выводы, рекомендации, проблемы) ===
    findings: list[Finding] = Field(
        default_factory=list,
        description="Выводы, рекомендации, проблемы качества данных",
    )

    # === VALIDATION (результат проверки) ===
    validation: Optional[ValidationResult] = Field(
        default=None, description="Результат валидации от ValidatorAgent"
    )

    # === PLAN (план выполнения) ===
    plan: Optional[Plan] = Field(
        default=None, description="План выполнения от PlannerAgent"
    )

    # === METADATA (агент-специфичные данные) ===
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Агент-специфичные данные (widget_type и др.)",
    )

    # === TOOLS (запросы и результаты инструментов) ===
    tool_requests: list[ToolRequest] = Field(
        default_factory=list,
        description="Запросы инструментов от агента (для orchestrator tool loop)",
    )
    tool_results: list[ToolResult] = Field(
        default_factory=list,
        description="Результаты инструментов, доступные агенту в следующем вызове",
    )

    # === ERROR (при status='error') ===
    error: Optional[str] = Field(
        default=None, description="Сообщение об ошибке"
    )
    suggestions: list[str] = Field(
        default_factory=list, description="Подсказки для recovery"
    )

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------

    @classmethod
    def success(
        cls,
        agent: str,
        *,
        narrative: Narrative | None = None,
        tables: list[PayloadContentTable] | None = None,
        code_blocks: list[CodeBlock] | None = None,
        sources: list[Source] | None = None,
        discovered_resources: list[DiscoveredResource] | None = None,
        findings: list[Finding] | None = None,
        validation: ValidationResult | None = None,
        plan: Plan | None = None,
        metadata: dict[str, Any] | None = None,
        tool_requests: list[ToolRequest] | None = None,
        tool_results: list[ToolResult] | None = None,
    ) -> "AgentPayload":
        """Создать успешный AgentPayload."""
        return cls(
            status="success",
            agent=agent,
            narrative=narrative,
            tables=tables or [],
            code_blocks=code_blocks or [],
            sources=sources or [],
            discovered_resources=discovered_resources or [],
            findings=findings or [],
            validation=validation,
            plan=plan,
            metadata=metadata or {},
            tool_requests=tool_requests or [],
            tool_results=tool_results or [],
        )

    @classmethod
    def make_error(
        cls,
        agent: str,
        error_message: str,
        *,
        suggestions: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "AgentPayload":
        """Создать AgentPayload с ошибкой."""
        return cls(
            status="error",
            agent=agent,
            error=error_message,
            suggestions=suggestions or [],
            metadata=metadata or {},
        )

    @classmethod
    def partial(
        cls,
        agent: str,
        **kwargs: Any,
    ) -> "AgentPayload":
        """Создать частичный результат (промежуточные данные)."""
        return cls(status="partial", agent=agent, **kwargs)

    # ------------------------------------------------------------------
    # Accessor helpers
    # ------------------------------------------------------------------

    def get_code(self, purpose: str = "transformation") -> CodeBlock | None:
        """Найти первый CodeBlock с указанным purpose."""
        return next(
            (cb for cb in self.code_blocks if cb.purpose == purpose), None
        )

    def get_table(self, name: str) -> PayloadContentTable | None:
        """Найти таблицу по имени."""
        return next((t for t in self.tables if t.name == name), None)

    def get_findings_by_type(self, finding_type: str) -> list[Finding]:
        """Отфильтровать findings по типу."""
        return [f for f in self.findings if f.type == finding_type]

    @property
    def is_valid(self) -> bool:
        """Результат прошёл валидацию (от ValidatorAgent)."""
        return self.validation is not None and self.validation.valid

    @property
    def has_code(self) -> bool:
        """Есть ли сгенерированный код."""
        return len(self.code_blocks) > 0

    @property
    def has_tables(self) -> bool:
        """Есть ли структурированные данные."""
        return len(self.tables) > 0

    def merge_from(self, other: "AgentPayload") -> None:
        """Дополнить текущий payload данными из другого (для ReporterAgent).

        Аддитивно добавляет tables, code_blocks, sources, findings.
        Не перезаписывает narrative, validation, plan — они агент-специфичны.
        """
        self.tables.extend(other.tables)
        self.code_blocks.extend(other.code_blocks)
        self.sources.extend(other.sources)
        self.discovered_resources.extend(other.discovered_resources)
        self.findings.extend(other.findings)
        # metadata — shallow merge
        for k, v in other.metadata.items():
            if k not in self.metadata:
                self.metadata[k] = v
