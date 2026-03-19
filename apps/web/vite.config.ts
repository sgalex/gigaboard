import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// docker-compose.dev: VITE_DEV_PROXY_TARGET=http://backend:8000
// Локальный Vite + только Docker nginx на хосте (без :8000): VITE_DEV_PROXY_TARGET=http://localhost:3000
const devProxyTarget = process.env.VITE_DEV_PROXY_TARGET || 'http://localhost:8000'

const devProxy = {
    target: devProxyTarget,
    changeOrigin: true,
}

export default defineConfig({
    plugins: [react()],
    resolve: {
        alias: {
            '@': path.resolve(__dirname, './src'),
        },
    },
    server: {
        port: 5173,
        proxy: {
            '/api': devProxy,
            '/socket.io': { ...devProxy, ws: true },
            // Как в nginx Docker-образа: health и Swagger через тот же target
            '/health': devProxy,
            '/docs': devProxy,
            '/openapi.json': devProxy,
            '/redoc': devProxy,
        }
    }
})
