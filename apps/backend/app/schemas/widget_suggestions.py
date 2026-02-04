from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from enum import Enum


class SuggestionType(str, Enum):
    """Types of widget suggestions."""
    IMPROVEMENT = "improvement"
    ALTERNATIVE = "alternative"
    INSIGHT = "insight"
    LIBRARY = "library"
    STYLE = "style"


class SuggestionPriority(str, Enum):
    """Priority levels for suggestions."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Suggestion(BaseModel):
    """Single widget improvement suggestion."""
    id: str = Field(..., description="Unique suggestion ID")
    type: SuggestionType = Field(..., description="Type of suggestion")
    priority: SuggestionPriority = Field(..., description="Priority level")
    title: str = Field(..., description="Short title (< 50 chars)")
    description: str = Field(..., description="Detailed description")
    prompt: str = Field(..., description="Ready-to-send user prompt")
    reasoning: str = Field("", description="Why this suggestion is useful")


class SuggestionAnalysisRequest(BaseModel):
    """Request for widget suggestions analysis."""
    chat_history: List[Dict[str, str]] = Field(
        default_factory=list, 
        description="Chat history for context"
    )
    current_widget_code: Optional[str] = Field(
        None, 
        description="Current widget HTML code"
    )
    max_suggestions: int = Field(
        5, 
        ge=1, 
        le=10, 
        description="Max number of suggestions"
    )


class SuggestionAnalysisResponse(BaseModel):
    """Response with widget suggestions."""
    suggestions: List[Suggestion] = Field(..., description="List of suggestions")
    analysis_summary: Dict[str, str] = Field(..., description="Summary of analysis")
