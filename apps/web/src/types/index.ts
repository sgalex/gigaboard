/**
 * TypeScript types for GigaBoard entities
 * Architecture: Data-Centric Canvas with SourceNode/ContentNode/WidgetNode/CommentNode
 */

// Project
export enum EdgeType {
    // v2.0: EXTRACT удалён — SourceNode теперь наследует ContentNode
    TRANSFORMATION = 'TRANSFORMATION',  // SourceNode/ContentNode → ContentNode
    VISUALIZATION = 'VISUALIZATION',    // SourceNode/ContentNode → WidgetNode
    COMMENT = 'COMMENT',
    DRILL_DOWN = 'DRILL_DOWN',
    REFERENCE = 'REFERENCE',
}

// Project
export interface Project {
    id: string;
    user_id: string;
    name: string;
    description: string | null;
    created_at: string;
    updated_at: string;
}

export interface ProjectWithBoards extends Project {
    boards_count: number;
    dashboards_count?: number;
    sources_count?: number;
    content_nodes_count?: number;
    widgets_count?: number;
    tables_count?: number;
    dimensions_count?: number;
    filters_count?: number;
}

export interface ProjectCreate {
    name: string;
    description?: string;
}

export interface ProjectUpdate {
    name?: string;
    description?: string;
}

// Board
export interface Board {
    id: string;
    project_id: string;
    user_id: string;
    name: string;
    description: string | null;
    thumbnail_url?: string | null;
    created_at: string;
    updated_at: string;
}

export interface BoardWithNodes extends Board {
    source_nodes_count?: number;
    content_nodes_count?: number;
    widget_nodes_count: number;
    comment_nodes_count: number;
    tables_count?: number;
    columns_count?: number;
}

export interface BoardCreate {
    project_id: string;
    name: string;
    description?: string;
}

export interface BoardUpdate {
    name?: string;
    description?: string;
    thumbnail_url?: string | null;
}

// Edge (Connection between nodes)
export interface Edge {
    id: string;
    board_id: string;
    source_node_id: string;
    target_node_id: string;
    source_node_type: string;  // 'source_node', 'content_node', 'widget_node', 'comment_node'
    target_node_type: string;
    edge_type: EdgeType;
    label: string | null;
    parameter_mapping: Record<string, string>;
    transformation_code: string | null;
    transformation_params: Record<string, any>;
    visual_config: EdgeVisualConfig;
    created_at: string;
    updated_at: string;
    is_valid: string;
    validation_errors: string | null;
}

export interface EdgeVisualConfig {
    color?: string;
    line_style?: 'solid' | 'dashed' | 'dotted';
    arrow_type?: 'forward' | 'bidirectional';
    animation?: 'flow' | 'pulse' | 'none';
}

export interface EdgeCreate {
    source_node_id: string;
    target_node_id: string;
    source_node_type: string;
    target_node_type: string;
    edge_type: EdgeType;
    label?: string;
    parameter_mapping?: Record<string, string>;
    transformation_code?: string;
    transformation_params?: Record<string, any>;
    visual_config?: EdgeVisualConfig;
}

export interface EdgeUpdate {
    label?: string;
    parameter_mapping?: Record<string, string>;
    visual_config?: EdgeVisualConfig;
}

export interface EdgeListResponse {
    edges: Edge[];
    total: number;
}

// ============================================
// NODE ARCHITECTURE WITH INHERITANCE
// ============================================

// Node Types
export enum NodeType {
    SOURCE_NODE = 'source_node',
    CONTENT_NODE = 'content_node',
    WIDGET_NODE = 'widget_node',
    COMMENT_NODE = 'comment_node',
}

// Base Node - parent interface for all node types
export interface BaseNode {
    id: string;
    board_id: string;
    node_type: NodeType;
    x: number;
    y: number;
    width?: number | null;
    height?: number | null;
    created_at: string;
    updated_at: string;
}



// ============================================
// SOURCE-CONTENT NODE ARCHITECTURE (FR-14) 🆕
// ============================================

// Source Types v2 - каждый тип файла отдельно
export enum SourceType {
    CSV = 'csv',              // CSV files
    JSON = 'json',            // JSON files
    EXCEL = 'excel',          // Excel files (xlsx, xls)
    DOCUMENT = 'document',    // PDF, DOCX, TXT
    API = 'api',              // REST API endpoint
    DATABASE = 'database',    // SQL databases
    RESEARCH = 'research',    // AI Deep Research
    MANUAL = 'manual',        // Manual data entry
    STREAM = 'stream',        // Real-time streams (Phase 4)
}

// SourceNode - point of data entry
// Now inherits ContentNode concept: contains both config and extracted data
export interface SourceNode extends BaseNode {
    node_type: NodeType.SOURCE_NODE;
    source_type: SourceType;
    config: Record<string, any>;
    metadata: Record<string, any>;
    position: { x: number; y: number };
    created_by: string;
    // ContentNode inheritance - extracted data
    content?: ContentData;
    lineage?: DataLineage;
}

export interface SourceNodeCreate {
    board_id: string;
    source_type: SourceType;
    config: Record<string, any>;
    metadata?: Record<string, any>;
    position?: { x: number; y: number };
    created_by: string;
    /** Pre-filled content (e.g. for RESEARCH: narrative + tables from dialog). */
    data?: { text?: string; tables?: Array<{ name?: string; columns?: Array<{ name: string; type?: string }>; rows?: Record<string, unknown>[]; row_count?: number; column_count?: number }> };
}

export interface SourceNodeUpdate {
    config?: Record<string, any>;
    metadata?: Record<string, any>;
    position?: { x: number; y: number };
    /** Обновление извлечённого контента (например document: text + tables из диалога). */
    data?: { text?: string; tables?: Array<Record<string, unknown>> };
}

// ContentNode - result of data processing
export interface ContentTable {
    name: string;
    columns: Array<{ name: string; type: string }>;
    rows: Array<Record<string, any>>;
    row_count: number;
    column_count: number;
    metadata?: Record<string, any>;
}

export interface ContentData {
    text?: string | null;
    tables: ContentTable[];
}

export interface TransformationStep {
    operation: string;
    description?: string;
    code_snippet?: string;
    timestamp: string;
    transformation_id?: string;
}

export interface DataLineage {
    source_node_id?: string;
    transformation_id?: string;
    operation: string;
    parent_content_ids?: string[];
    timestamp?: string;
    agent?: string;
    created_by?: string;
    // Legacy fields for backwards compatibility
    source_nodes?: string[];
    transformation_history?: TransformationStep[];
}

export interface ContentNode extends BaseNode {
    node_type: NodeType.CONTENT_NODE;
    content: ContentData;
    lineage: DataLineage;
    metadata: Record<string, any>;
    position: { x: number; y: number };
}

export interface ContentNodeCreate {
    board_id: string;
    content: ContentData | Record<string, any>;
    lineage: DataLineage | Record<string, any>;
    metadata?: Record<string, any>;
    position?: { x: number; y: number };
}

export interface ContentNodeUpdate {
    content?: ContentData | Record<string, any>;
    lineage?: DataLineage | Record<string, any>;
    metadata?: Record<string, any>;
    position?: { x: number; y: number };
}

// Visualize Request/Response 🆕
export interface VisualizeRequest {
    user_prompt?: string;
    auto_refresh?: boolean;
    position?: { x: number; y: number };
}

export interface VisualizeResponse {
    widget_node_id: string;
    edge_id: string;
    status: 'success' | 'error';
    error?: string;
}

// ============================================
// WIDGET NODE
// ============================================

// WidgetNode - contains AI-generated visualizations
export interface WidgetNode extends BaseNode {
    node_type: NodeType.WIDGET_NODE;
    name: string;
    description: string;  // User prompt describing the widget
    html_code: string;
    css_code: string | null;
    js_code: string | null;
    config: Record<string, any> | null;
    auto_refresh: boolean;
    refresh_interval: number | null;
    generated_by: string | null;
    generation_prompt: string | null;
}

export interface WidgetNodeCreate {
    name: string;
    description: string;
    html_code: string;
    css_code?: string;
    js_code?: string;
    config?: Record<string, any>;
    x?: number;
    y?: number;
    width?: number;
    height?: number;
    auto_refresh?: boolean;
    refresh_interval?: number;
    generated_by?: string;
    generation_prompt?: string;
}

export interface WidgetNodeUpdate {
    name?: string;
    description?: string;
    html_code?: string;
    css_code?: string;
    js_code?: string;
    config?: Record<string, any>;
    x?: number;
    y?: number;
    width?: number;
    height?: number;
    auto_refresh?: boolean;
    refresh_interval?: number;
}

// CommentNode - contains comments and annotations
export interface CommentNode extends BaseNode {
    node_type: NodeType.COMMENT_NODE;
    author_id: string;
    content: string;
    format_type: string;  // markdown, plain, html
    color: string | null;
    config: Record<string, any> | null;
    is_resolved: boolean;
    resolved_at: string | null;
    resolved_by: string | null;
}

export interface CommentNodeCreate {
    content: string;
    format_type?: string;
    color?: string;
    config?: Record<string, any>;
    x?: number;
    y?: number;
    width?: number;
    height?: number;
}

export interface CommentNodeUpdate {
    content?: string;
    format_type?: string;
    color?: string;
    config?: Record<string, any>;
    x?: number;
    y?: number;
    width?: number;
    height?: number;
    is_resolved?: boolean;
}

// AI Assistant types
export enum MessageRole {
    USER = 'user',
    ASSISTANT = 'assistant',
    SYSTEM = 'system',
}

export interface ChatMessage {
    id: string;
    board_id: string;
    user_id: string;
    session_id: string;
    role: MessageRole;
    content: string;
    context?: Record<string, any>;
    suggested_actions?: any[];
    created_at: string;
}

export interface AIChatRequest {
    message: string;
    session_id?: string;
    context?: {
        mode?: 'board' | 'dashboard';
        selected_nodes?: string[];
        selected_node_ids?: string[];
        allow_auto_filter?: boolean;
        required_tables?: string[];
        filter_expression?: Record<string, any>;
        [key: string]: any;
    };
}

export interface AIContextUsedTable {
    node_id?: string;
    node_name?: string;
    table_name?: string;
    row_count_before?: number;
    row_count_after?: number;
    row_count_after_is_sample?: boolean;
}

export interface AIContextUsed {
    scope?: 'board' | 'dashboard' | string;
    filters?: Record<string, any> | null;
    proposed_filters?: Record<string, any> | null;
    filter_applied_for_answer?: boolean;
    tables?: AIContextUsedTable[];
    [key: string]: any;
}

export interface AIChatResponse {
    response: string;
    session_id: string;
    suggested_actions?: any[];
    context_used?: AIContextUsed;
}

export interface AIChatHistoryResponse {
    messages: ChatMessage[];
    session_id: string | null;
    total_messages: number;
}

// Research Chat (ResearchSourceDialog)
export interface ResearchChatMessage {
    role: 'user' | 'assistant';
    content: string;
}

export interface ResearchSourceRef {
    url: string;
    title: string;
    /** MIME из ответа HTTP (research), если был fetch */
    mime_type?: string;
    /** Семантика ресурса: html_page, image, video, json, … */
    resource_kind?: string;
    metadata?: Record<string, unknown>;
}

/** Каталог URL из ResearchAgent (страницы + вложенные медиа и т.д.) */
export interface ResearchDiscoveredResourceRef {
    url: string;
    resource_kind?: string;
    mime_type?: string;
    parent_url?: string;
    origin?: string;
    tag?: string;
    title?: string;
}

export interface ResearchChatRequest {
    message: string;
    session_id?: string;
    chat_history?: ResearchChatMessage[];
}

export interface ResearchChatResponse {
    narrative: string;
    tables: Array<{ name?: string; columns?: Array<{ name: string; type?: string }>; rows?: Record<string, unknown>[] }>;
    sources: ResearchSourceRef[];
    discovered_resources?: ResearchDiscoveredResourceRef[];
    session_id: string;
    execution_time_ms?: number;
    plan?: Record<string, unknown>;
}

// API Response types
export interface ApiError {
    detail: string;
}
