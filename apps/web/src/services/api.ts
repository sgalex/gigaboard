import axios, { AxiosInstance } from 'axios'
import { useAuthStore } from '../store/authStore'
import { notify } from '@/store/notificationStore'
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
} from '@/types'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

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

// DataNodes API (Legacy - для обратной совместимости)
export const dataNodesAPI = {
    list: (boardId: string) => api.get<DataNode[]>(`/api/v1/boards/${boardId}/data-nodes`),
    create: (boardId: string, data: DataNodeCreate) =>
        api.post<DataNode>(`/api/v1/boards/${boardId}/data-nodes`, data),
    get: (boardId: string, dataNodeId: string) =>
        api.get<DataNode>(`/api/v1/boards/${boardId}/data-nodes/${dataNodeId}`),
    update: (boardId: string, dataNodeId: string, data: DataNodeUpdate) =>
        api.patch<DataNode>(`/api/v1/boards/${boardId}/data-nodes/${dataNodeId}`, data),
    delete: (boardId: string, dataNodeId: string) =>
        api.delete(`/api/v1/boards/${boardId}/data-nodes/${dataNodeId}`),
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
    extract: (sourceId: string, params?: { preview_rows?: number; position?: { x: number; y: number } }) =>
        api.post(`/api/v1/source-nodes/extract`, { source_node_id: sourceId, extraction_params: params || {} }),
    refresh: (sourceId: string) =>
        api.post<SourceNode>(`/api/v1/source-nodes/${sourceId}/refresh`),
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
    transformExecute: (boardId: string, contentId: string, params: { code: string; transformation_id?: string; description?: string; prompt?: string; target_node_id?: string }) =>
        api.post(`/api/v1/content-nodes/${contentId}/transform/execute`, params),
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

export default api
