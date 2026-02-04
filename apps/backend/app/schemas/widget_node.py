"""WidgetNode schemas."""
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.base_node import BaseNodeSchema, BaseNodeResponse


class WidgetNodeBase(BaseNodeSchema):
    """Base WidgetNode schema."""
    name: str = Field(..., max_length=200, description="WidgetNode name")
    description: str = Field(..., description="User prompt describing the widget")
    html_code: str = Field(..., description="AI-generated HTML code")
    css_code: str | None = Field(None, description="AI-generated CSS code")
    js_code: str | None = Field(None, description="AI-generated JavaScript code")
    config: dict[str, Any] | None = Field(None, description="Additional configuration")
    auto_refresh: bool = Field(default=True, description="Auto-refresh on data change")
    refresh_interval: int | None = Field(None, description="Refresh interval in seconds")


class WidgetNodeCreate(WidgetNodeBase):
    """Create WidgetNode schema."""
    generated_by: str | None = Field(None, description="Generator identifier")
    generation_prompt: str | None = Field(None, description="Original user prompt")


class WidgetNodeUpdate(BaseModel):
    """Update WidgetNode schema."""
    name: str | None = Field(None, max_length=200)
    description: str | None = None
    html_code: str | None = None
    css_code: str | None = None
    js_code: str | None = None
    config: dict[str, Any] | None = None
    x: int | None = None
    y: int | None = None
    width: int | None = None
    height: int | None = None
    auto_refresh: bool | None = None
    refresh_interval: int | None = None


class WidgetNodeResponse(BaseNodeResponse, WidgetNodeBase):
    """WidgetNode response schema."""
    generated_by: str | None
    generation_prompt: str | None
