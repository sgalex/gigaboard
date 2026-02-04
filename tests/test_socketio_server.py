import socketio
import uvicorn

# Простой Socket.IO сервер для тестирования
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=True,
    engineio_logger=True
)

app = socketio.ASGIApp(sio)

@sio.event
async def connect(sid, environ):
    print(f"Client {sid} connected")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
