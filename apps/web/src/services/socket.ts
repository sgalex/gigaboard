/**
 * Socket.IO Service - singleton для работы с Socket.IO вне React компонентов
 */
import { io, Socket } from 'socket.io-client'

const SOCKET_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

class SocketService {
    private socket: Socket | null = null
    private connected = false

    getSocket(): Socket | null {
        return this.socket
    }

    isConnected(): boolean {
        return this.connected && this.socket !== null && this.socket.connected
    }

    connect(token?: string): Socket {
        if (this.socket && this.socket.connected) {
            return this.socket
        }

        console.log('🔗 SocketService: Connecting...')

        this.socket = io(SOCKET_URL, {
            path: '/socket.io',
            transports: ['polling', 'websocket'],
            auth: token ? { token } : undefined,
            autoConnect: true,
            reconnection: true,
            reconnectionDelay: 1000,
            reconnectionAttempts: 5,
        })

        this.socket.on('connect', () => {
            console.log('✅ SocketService: Connected', this.socket?.id)
            this.connected = true
        })

        this.socket.on('disconnect', () => {
            console.log('🔌 SocketService: Disconnected')
            this.connected = false
        })

        this.socket.on('connect_error', (error) => {
            console.error('❌ SocketService: Connection error', error)
            this.connected = false
        })

        return this.socket
    }

    disconnect(): void {
        if (this.socket) {
            console.log('🔌 SocketService: Disconnecting...')
            this.socket.disconnect()
            this.socket = null
            this.connected = false
        }
    }

    emit(event: string, data: any): void {
        if (!this.socket) {
            console.warn('⚠️ SocketService: Cannot emit, not connected')
            return
        }
        this.socket.emit(event, data)
    }

    on(event: string, handler: (...args: any[]) => void): void {
        if (!this.socket) {
            console.warn('⚠️ SocketService: Cannot listen, not connected')
            return
        }
        this.socket.on(event, handler)
    }

    off(event: string, handler?: (...args: any[]) => void): void {
        if (!this.socket) {
            return
        }
        if (handler) {
            this.socket.off(event, handler)
        } else {
            this.socket.off(event)
        }
    }
}

// Singleton instance
export const socketService = new SocketService()
