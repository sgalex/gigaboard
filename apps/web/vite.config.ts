import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// В Docker (docker-compose.dev) задайте VITE_DEV_PROXY_TARGET=http://backend:8000
const devProxyTarget = process.env.VITE_DEV_PROXY_TARGET || 'http://localhost:8000'

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
            '/api': {
                target: devProxyTarget,
                changeOrigin: true,
            },
            '/socket.io': {
                target: devProxyTarget,
                changeOrigin: true,
                ws: true,
            },
        }
    }
})
