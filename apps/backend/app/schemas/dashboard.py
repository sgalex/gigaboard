"""Dashboard schemas."""
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, model_validator


# === Dashboard ===

class DashboardBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None


class DashboardCreate(DashboardBase):
    project_id: UUID
    settings: dict | None = None


class DashboardUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    status: str | None = None  # draft, published, archived
    thumbnail_url: str | None = Field(None, max_length=500)
    settings: dict | None = None


class DashboardResponse(DashboardBase):
    id: UUID
    project_id: UUID
    created_by: UUID
    status: str = "draft"
    thumbnail_url: str | None = None
    settings: dict | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def ensure_canvas_settings(self) -> "DashboardResponse":
        """Ensure settings always has canvas_width and canvas_height for consistent editor/view."""
        if self.settings is None:
            self.settings = {
                "canvas_width": 1440,
                "canvas_height": 900,
                "canvas_preset": "hd",
                "theme": "light",
                "background_color": "#ffffff",
                "grid_snap": True,
                "grid_size": 8,
            }
            return self
        s = dict(self.settings)
        if "canvas_width" not in s:
            s["canvas_width"] = 1440
        if "canvas_height" not in s:
            s["canvas_height"] = 900
        self.settings = s
        return self

    class Config:
        from_attributes = True


class DashboardWithItemsResponse(DashboardResponse):
    items: list['DashboardItemResponse'] = []

    class Config:
        from_attributes = True


# === DashboardItem ===

class ItemLayout(BaseModel):
    """Layout for a single breakpoint."""
    x: float = 0
    y: float = 0
    width: float = 400
    height: float = 300
    visible: bool = True


class DashboardItemBase(BaseModel):
    item_type: str  # widget, table, text, image, line
    source_id: UUID | None = None


class DashboardItemCreate(DashboardItemBase):
    layout: dict | None = None  # { desktop: {x,y,w,h,visible}, tablet: null, mobile: null }
    overrides: dict | None = None
    content: dict | None = None  # For text/image items
    z_index: int = 0


class DashboardItemUpdate(BaseModel):
    layout: dict | None = None
    overrides: dict | None = None
    content: dict | None = None
    z_index: int | None = None


class DashboardItemResponse(DashboardItemBase):
    id: UUID
    dashboard_id: UUID
    layout: dict
    overrides: dict | None = None
    content: dict | None = None
    z_index: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BatchItemUpdate(BaseModel):
    """Update multiple items at once (e.g., after rearranging)."""
    id: UUID
    layout: dict | None = None
    z_index: int | None = None


class BatchItemUpdateRequest(BaseModel):
    items: list[BatchItemUpdate]


# === DashboardShare ===

class DashboardShareCreate(BaseModel):
    share_type: str = "public"  # public, password, private
    password: str | None = None
    expires_at: datetime | None = None
    max_views: int | None = None
    allow_download: bool = False
    branding: dict | None = None


class DashboardShareResponse(BaseModel):
    id: UUID
    dashboard_id: UUID
    share_type: str
    share_token: str
    share_url: str | None = None  # computed in route
    expires_at: datetime | None = None
    max_views: int | None = None
    view_count: int = 0
    allow_download: bool = False
    branding: dict | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class PublicDashboardResponse(BaseModel):
    """Public dashboard data (no auth required)."""
    id: UUID
    name: str
    description: str | None = None
    settings: dict | None = None
    items: list[DashboardItemResponse] = []
    allow_download: bool = False
