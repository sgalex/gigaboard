"""
Transform-related Pydantic schemas.
"""
from pydantic import BaseModel, Field


# ==================== Transform Iterative Endpoint ====================

class TransformIterativeRequest(BaseModel):
    """Request for iterative transformation generation."""
    user_prompt: str = Field(..., description="User instruction for transformation")
    existing_code: str | None = Field(None, description="Current transformation code (for improvements)")
    transformation_id: str | None = Field(None, description="Session ID for tracking")
    chat_history: list[dict[str, str]] = Field(default_factory=list, description="Full chat context")
    selected_node_ids: list[str] = Field(default_factory=list, description="Multi-node support")
    preview_only: bool = Field(True, description="Don't create node, just preview")


class ValidationResult(BaseModel):
    """Code validation result."""
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[dict[str, str]] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class AgentPlanInfo(BaseModel):
    """Multi-agent execution plan."""
    steps: list[str] = Field(default_factory=list)
    attempts: int = 1
    total_time_ms: int = 0


class PreviewTable(BaseModel):
    """Preview table structure."""
    name: str
    columns: list[str]
    rows: list[list]
    row_count: int
    preview_row_count: int


class PreviewData(BaseModel):
    """Quick preview data."""
    tables: list[PreviewTable]
    execution_time_ms: int


class TransformIterativeResponse(BaseModel):
    """Response for iterative transformation."""
    transformation_id: str = Field(..., description="Session ID")
    code: str = Field(..., description="Generated/improved Python code")
    description: str = Field(..., description="AI explanation of changes")
    preview_data: PreviewData | None = Field(None, description="Quick preview results")
    validation: ValidationResult
    agent_plan: AgentPlanInfo


# ==================== Transform Suggestions Endpoint ====================

class TransformSuggestionsRequest(BaseModel):
    """Request for transformation suggestions."""
    chat_history: list[dict[str, str]] = Field(default_factory=list)
    current_code: str | None = Field(None, description="Existing transformation code")


class TransformSuggestion(BaseModel):
    """Single transformation suggestion."""
    id: str
    label: str = Field(..., description="Short label (2-4 words)")
    prompt: str = Field(..., description="Full prompt for AI")
    category: str = Field(..., description="filter|aggregate|merge|reshape|compute")
    confidence: float = Field(..., description="0.0-1.0")
    description: str | None = Field(None, description="Detailed description")
    reasoning: str | None = Field(None, description="Why this suggestion")


class TransformSuggestionsResponse(BaseModel):
    """Response with transformation suggestions."""
    suggestions: list[TransformSuggestion]
