import axios, { AxiosInstance } from 'axios'
import { useAuthStore } from '../store/authStore'
import { notify } from '@/store/notificationStore'
import { getViteApiBaseUrl } from '@/config/apiBase'
import type {
    Project,
    ProjectWithBoards,
    ProjectCreate,
    ProjectUpdate,
    Board,
    BoardWithNodes,
    BoardCreate,
    BoardUpdate,
    SourceNode,
    SourceNodeCreate,
    SourceNodeUpdate,
    ContentNode,
    ContentNodeCreate,
    ContentNodeUpdate,
    WidgetNode,
    WidgetNodeCreate,
    WidgetNodeUpdate,
    CommentNode,
    CommentNodeCreate,
    CommentNodeUpdate,
    Edge,
    EdgeCreate,
    EdgeUpdate,
    EdgeListResponse,
    AIChatRequest,
    AIChatResponse,
    AIChatHistoryResponse,
    ResearchChatRequest,
    ResearchChatResponse,
} from '@/types'
import type {
    ProjectWidget, ProjectWidgetCreate, ProjectWidgetUpdate,
    ProjectTable, ProjectTableCreate, ProjectTableUpdate,
    Dashboard, DashboardCreate, DashboardUpdate, DashboardWithItems,
    DashboardItem, DashboardItemCreate, DashboardItemUpdate,
    BatchItemUpdate,
    DashboardShare, DashboardShareCreate,
    PublicDashboard,
} from '@/types/dashboard'

/** Пустой env → относительные URL (Vite proxy / nginx в Docker). Не использовать `|| localhost:8000`: пустая строка falsy и уводила бы UI на хостовый :8000. */
const API_URL = getViteApiBaseUrl()

const api: AxiosInstance = axios.create({
    baseURL: API_URL,
})

// Add token to requests
api.interceptors.request.use((config) => {
    const token = useAuthStore.getState().token
    if (token) {
        config.headers.Authorization = `Bearer ${token}`
    }
    return config
})

// Handle errors
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (!error.response) {
            notify.error('Сервер недоступен или CORS блокирует запрос. Проверьте backend и VITE_API_URL.', {
                title: 'Сетевая ошибка',
            })
        }
        if (error.response?.status === 401) {
            useAuthStore.getState().logout()
            notify.info('Сессия истекла. Пожалуйста, войдите снова.', { title: 'Авторизация' })
        }
        return Promise.reject(error)
    }
)

// Auth API
export const authAPI = {
    register: (email: string, username: string, password: string) =>
        api.post('/api/v1/auth/register', { email, username, password }),
    login: (email: string, password: string) =>
        api.post('/api/v1/auth/login', { email, password }),
    logout: () => api.post('/api/v1/auth/logout'),
    getCurrentUser: () => api.get('/api/v1/auth/me'),
}

// Health API
export const healthAPI = {
    check: () => api.get('/health'),
    detailed: () => api.get('/api/v1/health'),
}

// Projects API
export const projectsAPI = {
    list: () => api.get<ProjectWithBoards[]>('/api/v1/projects'),
    create: (data: ProjectCreate) => api.post<Project>('/api/v1/projects', data),
    get: (id: string) => api.get<Project>(`/api/v1/projects/${id}`),
    update: (id: string, data: ProjectUpdate) => api.put<Project>(`/api/v1/projects/${id}`, data),
    delete: (id: string) => api.delete(`/api/v1/projects/${id}`),
}

// Boards API
export const boardsAPI = {
    list: (projectId?: string) => {
        const params = projectId ? { project_id: projectId } : {}
        return api.get<BoardWithNodes[]>('/api/v1/boards', { params })
    },
    create: (data: BoardCreate) => api.post<Board>('/api/v1/boards', data),
    get: (id: string) => api.get<Board>(`/api/v1/boards/${id}`),
    update: (id: string, data: BoardUpdate) => api.put<Board>(`/api/v1/boards/${id}`, data),
    delete: (id: string) => api.delete(`/api/v1/boards/${id}`),
}



// SourceNodes API (Source-Content Architecture) 🆕
export const sourceNodesAPI = {
    list: (boardId: string) => api.get<SourceNode[]>(`/api/v1/source-nodes/board/${boardId}`),
    create: (data: SourceNodeCreate) => api.post<SourceNode>('/api/v1/source-nodes', data),
    get: (sourceId: string) => api.get<SourceNode>(`/api/v1/source-nodes/${sourceId}`),
    update: (sourceId: string, data: SourceNodeUpdate) =>
        api.put<SourceNode>(`/api/v1/source-nodes/${sourceId}`, data),
    delete: (sourceId: string) => api.delete(`/api/v1/source-nodes/${sourceId}`),
    validate: (sourceId: string) =>
        api.post<{ valid: boolean; errors: string[] }>(`/api/v1/source-nodes/${sourceId}/validate`),
    // Operations
    extract: (boardId: string, sourceId: string, params?: { preview_rows?: number; position?: { x: number; y: number } }) =>
        api.post(`/api/v1/boards/${boardId}/source-nodes/${sourceId}/extract`, params || {}),
    refresh: (sourceId: string) =>
        api.post<SourceNode>(`/api/v1/source-nodes/${sourceId}/refresh`),
}

/** NDJSON: POST …/visualize-multiagent-stream, …/transform-multiagent-stream, …/files/…/extract-document-chat-stream. */
async function consumeContentNodeMultiagentNdjsonStream(
    apiPath: string,
    body: unknown,
    callbacks: {
        onPlanUpdate?: (steps: string[], meta?: { completedCount?: number }) => void
        onProgress?: (
            agentLabel: string,
            task: string,
            meta?: { stepIndex?: number; totalSteps?: number }
        ) => void
        onResult?: (result: Record<string, unknown>) => void
        onError?: (errorText: string) => void
    }
): Promise<void> {
    const token = useAuthStore.getState().token
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) {
        headers.Authorization = `Bearer ${token}`
    }
    const base = getViteApiBaseUrl()
    const url = base ? `${base.replace(/\/$/, '')}${apiPath}` : apiPath

    const res = await fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify(body),
    })

    if (!res.ok) {
        let detail = res.statusText
        try {
            const err = (await res.json()) as { detail?: string }
            if (err?.detail) detail = err.detail
        } catch {
            /* ignore */
        }
        callbacks.onError?.(String(detail))
        return
    }

    const reader = res.body?.getReader()
    if (!reader) {
        callbacks.onError?.('Пустой ответ сервера')
        return
    }

    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''
        for (const line of lines) {
            const trimmed = line.trim()
            if (!trimmed) continue
            let obj: Record<string, unknown>
            try {
                obj = JSON.parse(trimmed) as Record<string, unknown>
            } catch {
                continue
            }
            const t = obj.type
            if (t === 'plan') {
                const steps = Array.isArray(obj.steps) ? (obj.steps as string[]) : []
                const completedCount =
                    typeof obj.completed_count === 'number' ? obj.completed_count : 0
                callbacks.onPlanUpdate?.(steps, { completedCount })
            } else if (t === 'progress') {
                const agentLabel = String(obj.agent_label ?? obj.agent ?? '')
                const task = String(obj.task ?? '')
                const stepIndex =
                    typeof obj.step_index === 'number' ? obj.step_index : undefined
                const totalSteps =
                    typeof obj.total_steps === 'number' ? obj.total_steps : undefined
                callbacks.onProgress?.(agentLabel, task, { stepIndex, totalSteps })
            } else if (t === 'result') {
                const raw = obj.result
                if (raw && typeof raw === 'object') {
                    callbacks.onResult?.(raw as Record<string, unknown>)
                }
            } else if (t === 'error') {
                callbacks.onError?.(String(obj.error ?? 'Ошибка'))
            }
        }
    }
}

// ContentNodes API (Source-Content Architecture) 🆕
export const contentNodesAPI = {
    list: (boardId: string) => api.get<ContentNode[]>(`/api/v1/content-nodes/board/${boardId}`),
    create: (data: ContentNodeCreate) => api.post<ContentNode>('/api/v1/content-nodes', data),
    get: (contentId: string) => api.get<ContentNode>(`/api/v1/content-nodes/${contentId}`),
    update: (contentId: string, data: ContentNodeUpdate) =>
        api.put<ContentNode>(`/api/v1/content-nodes/${contentId}`, data),
    delete: (contentId: string) => api.delete(`/api/v1/content-nodes/${contentId}`),
    // Operations
    getTable: (contentId: string, tableId: string) =>
        api.post(`/api/v1/content-nodes/get-table`, { content_node_id: contentId, table_id: tableId }),
    getLineage: (contentId: string) =>
        api.get<Array<Record<string, any>>>(`/api/v1/content-nodes/${contentId}/lineage`),
    getDownstream: (contentId: string) =>
        api.get<ContentNode[]>(`/api/v1/content-nodes/${contentId}/downstream`),
    transform: (sourceContentIds: string[], transformationCode: string, outputDescription?: string) =>
        api.post(`/api/v1/content-nodes/transform`, {
            source_content_ids: sourceContentIds,
            transformation_code: transformationCode,
            output_description: outputDescription,
        }),
    transformSingle: (boardId: string, contentId: string, params: { prompt: string }) =>
        api.post(`/api/v1/content-nodes/${contentId}/transform`, params),
    // Two-step transformation workflow
    transformPreview: (boardId: string, contentId: string, params: { prompt: string }) =>
        api.post(`/api/v1/content-nodes/${contentId}/transform/preview`, params),
    transformExecute: (boardId: string, contentId: string, params: {
        code: string;
        transformation_id?: string;
        description?: string;
        prompt?: string;
        chat_history?: Array<{ role: string; content: string }>;
        target_node_id?: string;
        selected_node_ids?: string[];
    }) =>
        api.post(`/api/v1/content-nodes/${contentId}/transform/execute`, params),
    transformTest: (contentId: string, params: { code: string; transformation_id: string; selected_node_ids?: string[] }) =>
        api.post<{
            success: boolean;
            tables: Array<any>;
            execution_time_ms: number;
            row_counts: Record<string, number>;
            error?: string;
        }>(`/api/v1/content-nodes/${contentId}/transform/test`, params),
    // Transform via MultiAgent (with full validation workflow)
    transformMultiagent: (contentId: string, params: {
        user_prompt: string;
        existing_code?: string;
        transformation_id?: string;
        chat_history?: Array<{ role: string; content: string }>;
        selected_node_ids?: string[];
        preview_only?: boolean;
    }) =>
        api.post<{
            transformation_id: string;
            code: string;
            description: string;
            preview_data?: {
                tables: Array<any>;
                execution_time_ms: number;
            };
            validation: {
                is_valid: boolean;
                errors: string[];
            };
            agent_plan: any;
        }>(`/api/v1/content-nodes/${contentId}/transform-multiagent`, params),
    transformMultiagentStream: async (
        contentId: string,
        params: {
            user_prompt: string
            existing_code?: string
            transformation_id?: string
            chat_history?: Array<{ role: string; content: string }>
            selected_node_ids?: string[]
            preview_only?: boolean
        },
        callbacks: {
            onPlanUpdate?: (steps: string[], meta?: { completedCount?: number }) => void
            onProgress?: (
                agentLabel: string,
                task: string,
                meta?: { stepIndex?: number; totalSteps?: number }
            ) => void
            onResult?: (result: Record<string, unknown>) => void
            onError?: (errorText: string) => void
        }
    ) =>
        consumeContentNodeMultiagentNdjsonStream(
            `/api/v1/content-nodes/${contentId}/transform-multiagent-stream`,
            params,
            callbacks
        ),
    // Visualization
    visualize: (contentId: string, params: {
        user_prompt?: string;
        auto_refresh?: boolean;
        position?: { x: number; y: number };
    }) =>
        api.post(`/api/v1/content-nodes/${contentId}/visualize`, params),
    // Iterative visualization (for interactive editor)
    visualizeIterative: (contentId: string, params: {
        user_prompt: string;
        existing_html?: string;
        existing_css?: string;
        existing_js?: string;
        existing_widget_code?: string;
        chat_history?: Array<{ role: string; content: string }>;
    }) =>
        api.post<{
            html_code: string;
            css_code: string;
            js_code: string;
            widget_code?: string;  // Full HTML widget code (new format)
            widget_name?: string;  // Short widget name
            description: string;
            status: string;
            error?: string;
        }>(`/api/v1/content-nodes/${contentId}/visualize-iterative`, params),
    // Iterative visualization via MultiAgent (with full validation workflow)
    visualizeMultiagent: (contentId: string, params: {
        user_prompt: string;
        existing_html?: string;
        existing_css?: string;
        existing_js?: string;
        existing_widget_code?: string;
        chat_history?: Array<{ role: string; content: string }>;
    }) =>
        api.post<{
            html_code: string;
            css_code: string;
            js_code: string;
            widget_code?: string;  // Full HTML widget code (new format)
            widget_name?: string;  // Short widget name
            description: string;
            status: string;
            error?: string;
        }>(`/api/v1/content-nodes/${contentId}/visualize-multiagent`, params),
    visualizeMultiagentStream: async (
        contentId: string,
        params: {
            user_prompt: string
            existing_html?: string
            existing_css?: string
            existing_js?: string
            existing_widget_code?: string
            chat_history?: Array<{ role: string; content: string }>
            selected_node_ids?: string[]
        },
        callbacks: {
            onPlanUpdate?: (steps: string[], meta?: { completedCount?: number }) => void
            onProgress?: (
                agentLabel: string,
                task: string,
                meta?: { stepIndex?: number; totalSteps?: number }
            ) => void
            onResult?: (result: Record<string, unknown>) => void
            onError?: (errorText: string) => void
        }
    ) =>
        consumeContentNodeMultiagentNdjsonStream(
            `/api/v1/content-nodes/${contentId}/visualize-multiagent-stream`,
            params,
            callbacks
        ),
    // Widget suggestions
    analyzeSuggestions: (contentId: string, params: {
        chat_history: Array<{ role: string; content: string }>;
        current_widget_code?: string | null;
        max_suggestions?: number;
    }) =>
        api.post<{
            suggestions: Array<{
                id: string;
                type: 'improvement' | 'alternative' | 'insight' | 'library' | 'style';
                priority: 'high' | 'medium' | 'low';
                title: string;
                description: string;
                prompt: string;
                reasoning?: string;
            }>;
            analysis_summary: {
                data_structure: string;
                current_visualization: string;
                chat_context: string;
            };
        }>(`/api/v1/content-nodes/${contentId}/analyze-suggestions`, params),
    // Transform suggestions
    analyzeTransformSuggestions: (contentId: string, params: {
        chat_history: Array<{ role: string; content: string }>;
        current_code?: string | null;
    }) =>
        api.post<{
            suggestions: Array<{
                id: string;
                label: string;
                prompt: string;
                category: 'filter' | 'aggregate' | 'merge' | 'reshape' | 'compute';
                confidence: number;
                description?: string;
                reasoning?: string;
            }>;
        }>(`/api/v1/content-nodes/${contentId}/analyze-transform-suggestions`, params),
}

// WidgetNodes API
export const widgetNodesAPI = {
    list: (boardId: string) => api.get<WidgetNode[]>(`/api/v1/boards/${boardId}/widget-nodes`),
    create: (boardId: string, data: WidgetNodeCreate) =>
        api.post<WidgetNode>(`/api/v1/boards/${boardId}/widget-nodes`, data),
    get: (boardId: string, widgetNodeId: string) =>
        api.get<WidgetNode>(`/api/v1/boards/${boardId}/widget-nodes/${widgetNodeId}`),
    update: (boardId: string, widgetNodeId: string, data: WidgetNodeUpdate) =>
        api.patch<WidgetNode>(`/api/v1/boards/${boardId}/widget-nodes/${widgetNodeId}`, data),
    delete: (boardId: string, widgetNodeId: string) =>
        api.delete(`/api/v1/boards/${boardId}/widget-nodes/${widgetNodeId}`),
}

// CommentNodes API
export const commentNodesAPI = {
    list: (boardId: string) => api.get<CommentNode[]>(`/api/v1/boards/${boardId}/comment-nodes`),
    create: (boardId: string, data: CommentNodeCreate) =>
        api.post<CommentNode>(`/api/v1/boards/${boardId}/comment-nodes`, data),
    get: (boardId: string, commentNodeId: string) =>
        api.get<CommentNode>(`/api/v1/boards/${boardId}/comment-nodes/${commentNodeId}`),
    update: (boardId: string, commentNodeId: string, data: CommentNodeUpdate) =>
        api.patch<CommentNode>(`/api/v1/boards/${boardId}/comment-nodes/${commentNodeId}`, data),
    delete: (boardId: string, commentNodeId: string) =>
        api.delete(`/api/v1/boards/${boardId}/comment-nodes/${commentNodeId}`),
    resolve: (boardId: string, commentNodeId: string, isResolved: boolean) =>
        api.post<CommentNode>(`/api/v1/boards/${boardId}/comment-nodes/${commentNodeId}/resolve`, {
            is_resolved: isResolved,
        }),
}

// Edges API
export const edgesAPI = {
    list: (boardId: string) => api.get<EdgeListResponse>(`/api/v1/boards/${boardId}/edges`),
    create: (boardId: string, data: EdgeCreate) =>
        api.post<Edge>(`/api/v1/boards/${boardId}/edges`, data),
    get: (boardId: string, edgeId: string) =>
        api.get<Edge>(`/api/v1/boards/${boardId}/edges/${edgeId}`),
    update: (boardId: string, edgeId: string, data: EdgeUpdate) =>
        api.patch<Edge>(`/api/v1/boards/${boardId}/edges/${edgeId}`, data),
    delete: (boardId: string, edgeId: string) =>
        api.delete(`/api/v1/boards/${boardId}/edges/${edgeId}`),
}

// Files API
export const filesAPI = {
    upload: (file: File) => {
        const formData = new FormData()
        formData.append('file', file)
        return api.post<{
            file_id: string
            filename: string
            mime_type: string
            size_bytes: number
            path: string
        }>('/api/v1/files/upload', formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        })
    },
    download: (fileId: string) => api.get(`/api/v1/files/download/${fileId}`, { responseType: 'blob' }),
    analyzeCSV: (fileId: string) => api.post<{
        delimiter: string
        encoding: string
        has_header: boolean
        rows_count: number
        columns: Array<{
            name: string
            type: string
            sample_values: string[]
        }>
        preview_rows: Array<Record<string, any>>
    }>(`/api/v1/files/${fileId}/analyze-csv`),

    analyzeExcel: (fileId: string) => api.post<{
        sheet_names: string[]
        sheets: Array<{
            name: string
            rows_count: number
            columns: Array<{
                name: string
                type: string
                sample_values: string[]
            }>
            preview_rows: Array<Record<string, any>>
        }>
        total_rows: number
    }>(`/api/v1/files/${fileId}/analyze-excel`),

    excelPreview: (fileId: string) => api.post<{
        sheets: Array<{
            name: string
            max_row: number
            max_col: number
            cells: (string | number | null)[][]
            visible_rows: number
            visible_cols: number
        }>
    }>(`/api/v1/files/${fileId}/excel-preview`),

    analyzeExcelSmart: (fileId: string, useAi: boolean = true) => api.post<{
        sheet_names: string[]
        sheets: Array<{
            sheet_name: string
            total_rows: number
            total_cols: number
            regions: Array<{
                sheet_name: string
                start_row: number
                start_col: number
                end_row: number
                end_col: number
                header_row: number | null
                confidence: number
                table_name: string
                columns: Array<{ name: string; type: string }>
                preview_rows: Array<Record<string, any>>
                row_count: number
                range_str: string
                detection_method: string
            }>
            grid_map: string[][]
            grid_rows: number
            grid_cols: number
        }>
        total_tables_found: number
        detection_method: string
    }>(`/api/v1/files/${fileId}/analyze-excel-smart`, null, {
        params: { use_ai: useAi },
    }),

    analyzeDocument: (fileId: string) => api.post<{
        document_type: string
        filename: string
        text: string
        text_length: number
        page_count: number | null
        tables: Array<{
            name: string
            columns: Array<{ name: string; type: string }>
            rows: Array<Record<string, any>>
            row_count: number
        }>
        table_count: number
        total_rows: number
        is_scanned: boolean
    }>(`/api/v1/files/${fileId}/analyze-document`),

    analyzeDocumentSuggestions: (
        fileId: string,
        body: {
            chat_history: Array<{ role: string; content: string }>
            document_text: string
            document_type: string
            filename: string
            page_count?: number | null
            existing_tables?: Array<Record<string, unknown>>
        },
    ) =>
        api.post<{
            suggestions: Array<Record<string, unknown>>
            fallback?: boolean
        }>(`/api/v1/files/${fileId}/analyze-document-suggestions`, body),

    extractDocumentChat: (fileId: string, params: {
        user_prompt: string
        document_text: string
        document_type: string
        filename: string
        page_count?: number | null
        existing_tables?: Array<Record<string, any>>
        chat_history?: Array<{ role: string; content: string }>
    }) => api.post<{
        narrative: string
        tables: Array<{
            name: string
            columns: Array<{ name: string; type: string }>
            rows: Array<Record<string, any>>
            row_count?: number
        }>
        findings: Array<{ type?: string; text: string }>
        status: string
        mode: string
        agent_plan: any
    }>(`/api/v1/files/${fileId}/extract-document-chat`, params),

    extractDocumentChatStream: async (
        fileId: string,
        params: {
            user_prompt: string
            document_text: string
            document_type: string
            filename: string
            page_count?: number | null
            existing_tables?: Array<Record<string, any>>
            chat_history?: Array<{ role: string; content: string }>
        },
        callbacks: {
            onPlanUpdate?: (steps: string[], meta?: { completedCount?: number }) => void
            onProgress?: (
                agentLabel: string,
                task: string,
                meta?: { stepIndex?: number; totalSteps?: number }
            ) => void
            onResult?: (result: Record<string, unknown>) => void
            onError?: (errorText: string) => void
        }
    ) =>
        consumeContentNodeMultiagentNdjsonStream(
            `/api/v1/files/${fileId}/extract-document-chat-stream`,
            params,
            callbacks
        ),
}

// AI Assistant API
export const aiAssistantAPI = {
    chat: (boardId: string, data: AIChatRequest) =>
        api.post<AIChatResponse>(`/api/v1/boards/${boardId}/ai/chat`, data),
    getMyHistory: (boardId: string, limit?: number) =>
        api.get<AIChatHistoryResponse>(`/api/v1/boards/${boardId}/ai/chat/history/me`, {
            params: { limit },
        }),
    getHistory: (boardId: string, sessionId: string, limit?: number) =>
        api.get<AIChatHistoryResponse>(`/api/v1/boards/${boardId}/ai/chat/history`, {
            params: { session_id: sessionId, limit },
        }),
    deleteSession: (boardId: string, sessionId: string) =>
        api.delete(`/api/v1/boards/${boardId}/ai/chat/session/${sessionId}`),
}

// Database API — connection testing, table introspection, preview
export interface DatabaseTableInfo {
    name: string
    schema_name: string
    row_count: number
    column_count: number
}

export interface DatabaseSchemaInfo {
    name: string
    tables: DatabaseTableInfo[]
    table_count: number
}

export interface DatabaseConnectionResponse {
    success: boolean
    database_type: string
    schemas: DatabaseSchemaInfo[]
    table_count: number
    server_version: string
}

export interface DatabaseColumnInfo {
    name: string
    type: string
    nullable: boolean
}

export interface DatabasePreviewResponse {
    success: boolean
    table_name: string
    columns: DatabaseColumnInfo[]
    rows: Record<string, any>[]
    total_rows: number
    preview_rows: number
}

export const databaseAPI = {
    testConnection: (params: {
        database_type: string
        host?: string
        port?: number
        database?: string
        user?: string
        password?: string
        uri?: string
        path?: string
    }) => api.post<DatabaseConnectionResponse>('/api/v1/database/test-connection', params),

    preview: (params: {
        database_type: string
        host?: string
        port?: number
        database?: string
        user?: string
        password?: string
        path?: string
        table_name: string
        schema_name?: string
        where_clause?: string
        limit?: number
    }) => api.post<DatabasePreviewResponse>('/api/v1/database/preview', params),

    tableColumns: (params: {
        database_type: string
        host?: string
        port?: number
        database?: string
        user?: string
        password?: string
        path?: string
        table_name: string
        schema_name?: string
    }) => api.post<{ success: boolean; table_name: string; columns: DatabaseColumnInfo[] }>(
        '/api/v1/database/table-columns', params),
}

// Library API — project widgets & tables
export const libraryAPI = {
    // Widgets
    listWidgets: (projectId: string) =>
        api.get<ProjectWidget[]>(`/api/v1/projects/${projectId}/library/widgets`),
    createWidget: (projectId: string, data: ProjectWidgetCreate) =>
        api.post<ProjectWidget>(`/api/v1/projects/${projectId}/library/widgets`, data),
    getWidget: (projectId: string, widgetId: string) =>
        api.get<ProjectWidget>(`/api/v1/projects/${projectId}/library/widgets/${widgetId}`),
    updateWidget: (projectId: string, widgetId: string, data: ProjectWidgetUpdate) =>
        api.put<ProjectWidget>(`/api/v1/projects/${projectId}/library/widgets/${widgetId}`, data),
    deleteWidget: (projectId: string, widgetId: string) =>
        api.delete(`/api/v1/projects/${projectId}/library/widgets/${widgetId}`),

    // Tables
    listTables: (projectId: string) =>
        api.get<ProjectTable[]>(`/api/v1/projects/${projectId}/library/tables`),
    createTable: (projectId: string, data: ProjectTableCreate) =>
        api.post<ProjectTable>(`/api/v1/projects/${projectId}/library/tables`, data),
    getTable: (projectId: string, tableId: string) =>
        api.get<ProjectTable>(`/api/v1/projects/${projectId}/library/tables/${tableId}`),
    updateTable: (projectId: string, tableId: string, data: ProjectTableUpdate) =>
        api.put<ProjectTable>(`/api/v1/projects/${projectId}/library/tables/${tableId}`, data),
    deleteTable: (projectId: string, tableId: string) =>
        api.delete(`/api/v1/projects/${projectId}/library/tables/${tableId}`),
}

// Dashboards API
export const dashboardsAPI = {
    list: (projectId: string) =>
        api.get<Dashboard[]>('/api/v1/dashboards', { params: { project_id: projectId } }),
    create: (data: DashboardCreate) =>
        api.post<Dashboard>('/api/v1/dashboards', data),
    get: (id: string) =>
        api.get<DashboardWithItems>(`/api/v1/dashboards/${id}`),
    update: (id: string, data: DashboardUpdate) =>
        api.put<Dashboard>(`/api/v1/dashboards/${id}`, data),
    delete: (id: string) =>
        api.delete(`/api/v1/dashboards/${id}`),

    // Items
    addItem: (dashboardId: string, data: DashboardItemCreate) =>
        api.post<DashboardItem>(`/api/v1/dashboards/${dashboardId}/items`, data),
    updateItem: (dashboardId: string, itemId: string, data: DashboardItemUpdate) =>
        api.put<DashboardItem>(`/api/v1/dashboards/${dashboardId}/items/${itemId}`, data),
    removeItem: (dashboardId: string, itemId: string) =>
        api.delete(`/api/v1/dashboards/${dashboardId}/items/${itemId}`),
    batchUpdateItems: (dashboardId: string, items: BatchItemUpdate[]) =>
        api.put<DashboardItem[]>(`/api/v1/dashboards/${dashboardId}/items`, { items }),
    duplicateItem: (dashboardId: string, itemId: string) =>
        api.post<DashboardItem>(`/api/v1/dashboards/${dashboardId}/items/${itemId}/duplicate`),

    // Sharing
    createShare: (dashboardId: string, data: DashboardShareCreate) =>
        api.post<DashboardShare>(`/api/v1/dashboards/${dashboardId}/share`, data),
    getShare: (dashboardId: string) =>
        api.get<DashboardShare>(`/api/v1/dashboards/${dashboardId}/share`),
    deleteShare: (dashboardId: string) =>
        api.delete(`/api/v1/dashboards/${dashboardId}/share`),
}

// Public API — unauthenticated
export const publicAPI = {
    getDashboard: (token: string, password?: string) =>
        api.get<PublicDashboard>(`/api/v1/public/dashboards/${token}`, {
            params: password ? { password } : {},
        }),
}

// ══════════════════════════════════════════════════════════════════════
// Cross-Filter System API — see docs/CROSS_FILTER_SYSTEM.md
// ══════════════════════════════════════════════════════════════════════

import type {
    Dimension, DimensionCreate, DimensionUpdate,
    DimensionColumnMapping, DimensionColumnMappingCreate,
    DimensionSuggestion,
    FilterPreset, FilterPresetCreate, FilterPresetUpdate,
    ActiveFiltersResponse, FilterExpression,
} from '@/types/crossFilter'

// Dimensions API
export const dimensionsAPI = {
    list: (projectId: string) =>
        api.get<Dimension[]>(`/api/v1/projects/${projectId}/dimensions`),
    create: (projectId: string, data: DimensionCreate) =>
        api.post<Dimension>(`/api/v1/projects/${projectId}/dimensions`, data),
    get: (projectId: string, dimId: string) =>
        api.get<Dimension>(`/api/v1/projects/${projectId}/dimensions/${dimId}`),
    update: (projectId: string, dimId: string, data: DimensionUpdate) =>
        api.put<Dimension>(`/api/v1/projects/${projectId}/dimensions/${dimId}`, data),
    delete: (projectId: string, dimId: string) =>
        api.delete(`/api/v1/projects/${projectId}/dimensions/${dimId}`),

    mergeDimensions: (
        projectId: string,
        data: { source_ids: string[]; target_id: string },
    ) =>
        api.post<{
            target_id: string
            deleted_count: number
            transferred_count: number
        }>(`/api/v1/projects/${projectId}/dimensions/merge`, data),

    // Mappings
    listMappings: (projectId: string, dimId: string) =>
        api.get<DimensionColumnMapping[]>(`/api/v1/projects/${projectId}/dimensions/${dimId}/mappings`),
    createMapping: (projectId: string, dimId: string, data: DimensionColumnMappingCreate) =>
        api.post<DimensionColumnMapping>(`/api/v1/projects/${projectId}/dimensions/${dimId}/mappings`, data),
    deleteMapping: (projectId: string, mappingId: string) =>
        api.delete(`/api/v1/projects/${projectId}/dimensions/mappings/${mappingId}`),

    // Values
    getValues: (projectId: string, dimId: string) =>
        api.get<{ values: any[]; total: number }>(`/api/v1/projects/${projectId}/dimensions/${dimId}/values`),

    // Node-level mappings
    getMappingsForNode: (nodeId: string) =>
        api.get<{ mappings: DimensionColumnMapping[] }>(`/api/v1/content-nodes/${nodeId}/dimension-mappings`),

    // Auto-detect dimensions from content node tables
    detectDimensions: (nodeId: string) =>
        api.post<{ suggestions: DimensionSuggestion[]; total_columns_scanned: number }>(`/api/v1/content-nodes/${nodeId}/detect-dimensions`),
}

// Filters API (board/dashboard active filters)
export const filtersAPI = {
    // Board
    getBoardFilters: (boardId: string) =>
        api.get<ActiveFiltersResponse>(`/api/v1/boards/${boardId}/filters`),
    setBoardFilters: (boardId: string, filters: FilterExpression | null) =>
        api.put<ActiveFiltersResponse>(`/api/v1/boards/${boardId}/filters`, { filters }),
    clearBoardFilters: (boardId: string) =>
        api.post<ActiveFiltersResponse>(`/api/v1/boards/${boardId}/filters/clear`),
    applyBoardPreset: (boardId: string, presetId: string) =>
        api.post<ActiveFiltersResponse>(`/api/v1/boards/${boardId}/filters/apply-preset/${presetId}`),
    /**
     * Пересчитать pandas-цепочку доски с фильтрами (без сохранения в БД).
     * ContentNode с ai_resolve_batch используют кэш + row-level filter.
     */
    computeFiltered: (boardId: string, filters: FilterExpression | null) =>
        api.post<{
            nodes: Record<string, { tables: any[]; uses_ai: boolean; from_cache: boolean }>
        }>(`/api/v1/boards/${boardId}/filters/compute-filtered`, { filters }),

    // Dashboard
    getDashboardFilters: (dashboardId: string) =>
        api.get<ActiveFiltersResponse>(`/api/v1/dashboards/${dashboardId}/filters`),
    setDashboardFilters: (dashboardId: string, filters: FilterExpression | null) =>
        api.put<ActiveFiltersResponse>(`/api/v1/dashboards/${dashboardId}/filters`, { filters }),
    clearDashboardFilters: (dashboardId: string) =>
        api.post<ActiveFiltersResponse>(`/api/v1/dashboards/${dashboardId}/filters/clear`),
    applyDashboardPreset: (dashboardId: string, presetId: string) =>
        api.post<ActiveFiltersResponse>(`/api/v1/dashboards/${dashboardId}/filters/apply-preset/${presetId}`),
}

// Filter Presets API (project-scoped)
export const filterPresetsAPI = {
    list: (projectId: string, scope?: string, targetId?: string) =>
        api.get<FilterPreset[]>(`/api/v1/projects/${projectId}/filter-presets`, {
            params: { ...(scope && { scope }), ...(targetId && { target_id: targetId }) },
        }),
    create: (projectId: string, data: FilterPresetCreate) =>
        api.post<FilterPreset>(`/api/v1/projects/${projectId}/filter-presets`, data),
    get: (projectId: string, presetId: string) =>
        api.get<FilterPreset>(`/api/v1/projects/${projectId}/filter-presets/${presetId}`),
    update: (projectId: string, presetId: string, data: FilterPresetUpdate) =>
        api.put<FilterPreset>(`/api/v1/projects/${projectId}/filter-presets/${presetId}`, data),
    delete: (projectId: string, presetId: string) =>
        api.delete(`/api/v1/projects/${projectId}/filter-presets/${presetId}`),
}

/** Research Chat (ResearchSourceDialog) — см. POST /api/v1/research/chat, /chat-stream */
export const researchAPI = {
    chat: (data: ResearchChatRequest) =>
        api.post<ResearchChatResponse>('/api/v1/research/chat', data),

    async chatStream(
        body: ResearchChatRequest,
        callbacks: {
            onPlanUpdate?: (steps: string[], meta?: { completedCount?: number }) => void
            onProgress?: (
                agentLabel: string,
                task: string,
                meta?: { stepIndex?: number; totalSteps?: number }
            ) => void
            onResult?: (result: ResearchChatResponse) => void
            onError?: (errorText: string) => void
        }
    ): Promise<void> {
        const token = useAuthStore.getState().token
        const headers: Record<string, string> = { 'Content-Type': 'application/json' }
        if (token) {
            headers.Authorization = `Bearer ${token}`
        }
        const base = getViteApiBaseUrl()
        const url = base
            ? `${base.replace(/\/$/, '')}/api/v1/research/chat-stream`
            : '/api/v1/research/chat-stream'

        const res = await fetch(url, {
            method: 'POST',
            headers,
            body: JSON.stringify(body),
        })

        if (!res.ok) {
            let detail = res.statusText
            try {
                const err = (await res.json()) as { detail?: string }
                if (err?.detail) detail = err.detail
            } catch {
                /* ignore */
            }
            callbacks.onError?.(String(detail))
            return
        }

        const reader = res.body?.getReader()
        if (!reader) {
            callbacks.onError?.('Пустой ответ сервера')
            return
        }

        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
            const { done, value } = await reader.read()
            if (done) break
            buffer += decoder.decode(value, { stream: true })
            const lines = buffer.split('\n')
            buffer = lines.pop() ?? ''
            for (const line of lines) {
                const trimmed = line.trim()
                if (!trimmed) continue
                let obj: Record<string, unknown>
                try {
                    obj = JSON.parse(trimmed) as Record<string, unknown>
                } catch {
                    continue
                }
                const t = obj.type
                if (t === 'plan') {
                    const steps = Array.isArray(obj.steps) ? (obj.steps as string[]) : []
                    const completedCount =
                        typeof obj.completed_count === 'number' ? obj.completed_count : 0
                    callbacks.onPlanUpdate?.(steps, { completedCount })
                } else if (t === 'progress') {
                    const agentLabel = String(obj.agent_label ?? obj.agent ?? '')
                    const task = String(obj.task ?? '')
                    const stepIndex =
                        typeof obj.step_index === 'number' ? obj.step_index : undefined
                    const totalSteps =
                        typeof obj.total_steps === 'number' ? obj.total_steps : undefined
                    callbacks.onProgress?.(agentLabel, task, { stepIndex, totalSteps })
                } else if (t === 'result') {
                    const raw = obj.result
                    if (raw && typeof raw === 'object') {
                        callbacks.onResult?.(raw as ResearchChatResponse)
                    }
                } else if (t === 'error') {
                    callbacks.onError?.(String(obj.error ?? 'Ошибка исследования'))
                }
            }
        }
    },
}

/** Публичный URL превью файла (картинки) для img src. */
export function getFileImageUrl(fileId: string): string {
    const path = `/api/v1/files/image/${fileId}`
    const base = getViteApiBaseUrl()
    if (!base) return path
    return `${base.replace(/\/$/, '')}${path}`
}

/**
 * URL для превью досок/дашбордов: относительные /api/... дополняются базой API;
 * абсолютные ссылки на тот же path перепривязываются к текущей базе (dev → nginx).
 */
export function getProxiedImageUrl(url: string | null | undefined): string | null {
    if (url == null || String(url).trim() === '') return null
    const s = String(url).trim()
    if (s.startsWith('blob:') || s.startsWith('data:')) return s

    if (s.startsWith('/api/')) {
        const base = getViteApiBaseUrl()
        return base ? `${base.replace(/\/$/, '')}${s}` : s
    }

    try {
        const u = new URL(s)
        if (u.pathname.includes('/api/v1/files/image/')) {
            const base = getViteApiBaseUrl()
            const path = `${u.pathname}${u.search}${u.hash}`
            if (!base) return path
            return `${base.replace(/\/$/, '')}${path}`
        }
    } catch {
        /* not a valid absolute URL */
    }

    if (/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(s)) {
        return getFileImageUrl(s)
    }

    return s
}

export default api
