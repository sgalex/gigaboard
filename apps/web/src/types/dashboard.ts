/**
 * Dashboard system types
 * See docs/DASHBOARD_SYSTEM.md
 */

// ── Library (Project Widgets & Tables) ────────────────

export interface ProjectWidget {
    id: string;
    project_id: string;
    created_by: string;
    name: string;
    description: string | null;
    html_code: string | null;
    css_code: string | null;
    js_code: string | null;
    thumbnail_url: string | null;
    source_widget_node_id: string | null;
    source_content_node_id: string | null;
    source_board_id: string | null;
    config: Record<string, any>;
    created_at: string;
    updated_at: string;
}

export interface ProjectWidgetCreate {
    name: string;
    description?: string;
    html_code?: string;
    css_code?: string;
    js_code?: string;
    source_widget_node_id?: string;
    source_content_node_id?: string;
    source_board_id?: string;
    config?: Record<string, any>;
}

export interface ProjectWidgetUpdate {
    name?: string;
    description?: string;
    html_code?: string;
    css_code?: string;
    js_code?: string;
    config?: Record<string, any>;
}

export interface ProjectTable {
    id: string;
    project_id: string;
    created_by: string;
    name: string;
    description: string | null;
    columns: Array<{ name: string; type: string }>;
    sample_data: Array<Record<string, any>>;
    row_count: number;
    source_content_node_id: string | null;
    source_board_id: string | null;
    table_name_in_node: string | null;
    config: Record<string, any>;
    created_at: string;
    updated_at: string;
}

export interface ProjectTableCreate {
    name: string;
    description?: string;
    columns?: Array<{ name: string; type: string }>;
    sample_data?: Array<Record<string, any>>;
    row_count?: number;
    source_content_node_id?: string;
    source_board_id?: string;
    table_name_in_node?: string;
    config?: Record<string, any>;
}

export interface ProjectTableUpdate {
    name?: string;
    description?: string;
    columns?: Array<{ name: string; type: string }>;
    sample_data?: Array<Record<string, any>>;
    row_count?: number;
    config?: Record<string, any>;
}

// ── Dashboard ─────────────────────────────────────────

export type DashboardStatus = 'draft' | 'published' | 'archived';
export type CanvasPreset = 'hd' | 'fullhd' | 'compact' | 'custom';
export type DashboardItemType = 'widget' | 'table' | 'text' | 'image' | 'line';

export interface DashboardSettings {
    canvas_width: number;
    canvas_height?: number;
    canvas_preset: CanvasPreset;
    theme: 'light' | 'dark';
    background_color: string;
    grid_snap: boolean;
    grid_size: number;
}

export interface Dashboard {
    id: string;
    project_id: string;
    created_by: string;
    name: string;
    description: string | null;
    status: DashboardStatus;
    /** URL of splash/preview image (e.g. from file upload when saving dashboard). */
    thumbnail_url?: string | null;
    settings: DashboardSettings;
    created_at: string;
    updated_at: string;
}

export interface DashboardCreate {
    project_id: string;
    name: string;
    description?: string;
    settings?: Partial<DashboardSettings>;
}

export interface DashboardUpdate {
    name?: string;
    description?: string;
    status?: DashboardStatus;
    thumbnail_url?: string | null;
    settings?: Partial<DashboardSettings>;
}

// ── Dashboard Items ───────────────────────────────────

export interface ItemBreakpointLayout {
    x: number;
    y: number;
    width: number;
    height: number;
    visible: boolean;
    rotation?: number;
}

export interface ItemLayout {
    desktop: ItemBreakpointLayout;
    tablet: ItemBreakpointLayout | null;
    mobile: ItemBreakpointLayout | null;
}

export interface DashboardItem {
    id: string;
    dashboard_id: string;
    item_type: DashboardItemType;
    source_id: string | null;
    layout: ItemLayout;
    overrides: Record<string, any>;
    content: Record<string, any>;
    z_index: number;
    created_at: string;
    updated_at: string;
}

export interface DashboardItemCreate {
    item_type: DashboardItemType;
    source_id?: string;
    layout?: Partial<ItemLayout>;
    overrides?: Record<string, any>;
    content?: Record<string, any>;
}

export interface DashboardItemUpdate {
    layout?: Partial<ItemLayout>;
    overrides?: Record<string, any>;
    content?: Record<string, any>;
    z_index?: number;
}

export interface BatchItemUpdate {
    id: string;
    layout?: Partial<ItemLayout>;
    z_index?: number;
}

export interface DashboardWithItems extends Dashboard {
    items: DashboardItem[];
}

// ── Sharing ───────────────────────────────────────────

export type ShareType = 'public' | 'password' | 'restricted';

export interface DashboardShare {
    id: string;
    dashboard_id: string;
    share_type: ShareType;
    share_token: string;
    expires_at: string | null;
    max_views: number | null;
    branding: Record<string, any>;
    view_count: number;
    allow_download: boolean;
    created_at: string;
    updated_at: string;
}

export interface DashboardShareCreate {
    share_type?: ShareType;
    password?: string;
    expires_at?: string;
    max_views?: number;
    allow_download?: boolean;
    branding?: Record<string, any>;
}

export interface PublicDashboard {
    id: string;
    name: string;
    description: string | null;
    settings: DashboardSettings;
    items: DashboardItem[];
}
