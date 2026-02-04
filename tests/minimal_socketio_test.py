from fastapi import FastAPI
import socketio
import uvicorn

# Create Socket.IO server
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')

# Create FastAPI app
fastapi_app = FastAPI()

@fastapi_app.get("/api/test")
async def test():
    return {"message": "FastAPI works"}

@sio.event
async def connect(sid, environ):
    print(f"Client {sid} connected")

# Wrap FastAPI with Socket.IO
app = socketio.ASGIApp(sio, fastapi_app)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
