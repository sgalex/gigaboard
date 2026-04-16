/**
 * Project Store - manages projects state
 */
import { create } from 'zustand'
import { projectsAPI } from '@/services/api'
import { notify } from './notificationStore'
import type { Project, ProjectWithBoards, ProjectCreate, ProjectUpdate } from '@/types'

interface ProjectStore {
    // State
    projects: ProjectWithBoards[]
    currentProject: Project | null
    isLoading: boolean
    error: string | null

    // Actions
    /** silent: обновить список без isLoading (например после импорта ZIP — сразу актуальные счётчики на карточке). */
    fetchProjects: (opts?: { silent?: boolean }) => Promise<void>
    createProject: (data: ProjectCreate) => Promise<Project | null>
    fetchProject: (id: string) => Promise<void>
    updateProject: (id: string, data: ProjectUpdate) => Promise<void>
    deleteProject: (id: string) => Promise<void>
    importProjectFromZip: (file: File, name?: string) => Promise<Project | null>
    setCurrentProject: (project: Project | null) => void
    clearError: () => void
}

export const useProjectStore = create<ProjectStore>((set, get) => ({
    // Initial state
    projects: [],
    currentProject: null,
    isLoading: false,
    error: null,

    // Fetch all projects
    fetchProjects: async (opts?: { silent?: boolean }) => {
        const silent = Boolean(opts?.silent)
        if (!silent) {
            set({ isLoading: true, error: null })
        }
        try {
            const response = await projectsAPI.list()
            set((state) => ({
                projects: response.data,
                ...(silent ? {} : { isLoading: false }),
                error: null,
            }))
        } catch (error: any) {
            const message = error.response?.data?.detail || 'Не удалось загрузить проекты'
            set((state) => ({
                ...(silent ? {} : { isLoading: false }),
                error: message,
            }))
            notify.error(message, { title: 'Ошибка загрузки' })
        }
    },

    // Create new project
    createProject: async (data: ProjectCreate) => {
        set({ isLoading: true, error: null })
        try {
            const response = await projectsAPI.create(data)
            const newProject = response.data

            // Add to projects list
            set((state) => ({
                projects: [{
                ...newProject,
                boards_count: 0,
                dashboards_count: 0,
                sources_count: 0,
                content_nodes_count: 0,
                widgets_count: 0,
                tables_count: 0,
                dimensions_count: 0,
                filters_count: 0,
            }, ...state.projects],
                isLoading: false,
            }))

            notify.success(`Проект "${newProject.name}" создан`, { title: 'Успех' })
            return newProject
        } catch (error: any) {
            const message = error.response?.data?.detail || 'Не удалось создать проект'
            set({ error: message, isLoading: false })
            notify.error(message, { title: 'Ошибка создания' })
            return null
        }
    },

    // Fetch single project
    fetchProject: async (id: string) => {
        set({ isLoading: true, error: null })
        try {
            const response = await projectsAPI.get(id)
            set({ currentProject: response.data, isLoading: false })
        } catch (error: any) {
            const message = error.response?.data?.detail || 'Не удалось загрузить проект'
            set({ error: message, isLoading: false, currentProject: null })
            notify.error(message, { title: 'Ошибка загрузки' })
        }
    },

    // Update project
    updateProject: async (id: string, data: ProjectUpdate) => {
        set({ isLoading: true, error: null })
        try {
            const response = await projectsAPI.update(id, data)
            const updatedProject = response.data

            // Update in projects list
            set((state) => ({
                projects: state.projects.map((p) =>
                    p.id === id ? { ...p, ...updatedProject } : p
                ),
                currentProject:
                    state.currentProject?.id === id ? updatedProject : state.currentProject,
                isLoading: false,
            }))

            notify.success('Проект обновлен', { title: 'Успех' })
        } catch (error: any) {
            const message = error.response?.data?.detail || 'Не удалось обновить проект'
            set({ error: message, isLoading: false })
            notify.error(message, { title: 'Ошибка обновления' })
        }
    },

    // Delete project
    deleteProject: async (id: string) => {
        set({ isLoading: true, error: null })
        try {
            await projectsAPI.delete(id)

            set((state) => ({
                projects: state.projects.filter((p) => p.id !== id),
                currentProject: state.currentProject?.id === id ? null : state.currentProject,
                isLoading: false,
            }))

            notify.success('Проект удален', { title: 'Успех' })
        } catch (error: any) {
            const message = error.response?.data?.detail || 'Не удалось удалить проект'
            set({ error: message, isLoading: false })
            notify.error(message, { title: 'Ошибка удаления' })
        }
    },

    importProjectFromZip: async (file: File, name?: string) => {
        set({ error: null })
        try {
            const response = await projectsAPI.importZip(file, name)
            const newProject = response.data
            await get().fetchProjects({ silent: true })
            notify.success(`Проект «${newProject.name}» импортирован`, { title: 'Импорт' })
            return newProject
        } catch (error: unknown) {
            const er = error as { response?: { data?: { detail?: string } }; message?: string }
            const message =
                er.response?.data?.detail ||
                er.message ||
                'Не удалось импортировать архив'
            set({ error: typeof message === 'string' ? message : 'Ошибка импорта' })
            notify.error(typeof message === 'string' ? message : 'Ошибка импорта', {
                title: 'Импорт',
            })
            return null
        }
    },

    // Set current project
    setCurrentProject: (project: Project | null) => {
        set({ currentProject: project })
    },

    // Clear error
    clearError: () => {
        set({ error: null })
    },
}))
