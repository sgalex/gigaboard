import React from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './store/authStore'
import { LandingPage } from './pages/LandingPage'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'
import { WelcomePage } from './pages/WelcomePage'
import { ProjectOverviewPage } from './pages/ProjectOverviewPage'
import { BoardPage } from './pages/BoardPage'
import { ProtectedRoute } from './components/ProtectedRoute'
import { ThemeProvider } from './components/ThemeProvider'
import { Toaster } from './components/notifications/Toaster'
import { CreateProjectDialog } from './components/dialogs/CreateProjectDialog'
import { CreateBoardDialog } from './components/dialogs/CreateBoardDialog'

function App() {
    return (
        <ThemeProvider defaultTheme="light" storageKey="gigaboard-theme">
            <Toaster />
            <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
                <CreateProjectDialog />
                <CreateBoardDialog />
                <Routes>
                    <Route path="/" element={<LandingPage />} />
                    <Route path="/login" element={<LoginPage />} />
                    <Route path="/register" element={<RegisterPage />} />
                    <Route
                        path="/welcome"
                        element={
                            <ProtectedRoute>
                                <WelcomePage />
                            </ProtectedRoute>
                        }
                    />
                    <Route
                        path="/project/:projectId"
                        element={
                            <ProtectedRoute>
                                <ProjectOverviewPage />
                            </ProtectedRoute>
                        }
                    />
                    <Route
                        path="/project/:projectId/board/:boardId"
                        element={
                            <ProtectedRoute>
                                <BoardPage />
                            </ProtectedRoute>
                        }
                    />
                    <Route path="*" element={<Navigate to="/welcome" replace />} />
                </Routes>
            </Router>
        </ThemeProvider>
    )
}

export default App
