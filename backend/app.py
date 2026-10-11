import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.database import engine, Base, AsyncSessionLocal
from backend.services.seed import seed_initial_data
from backend.services.websocket_manager import ws_manager

from backend.routers import access, gates, visitors, alerts, telemetry

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables & seed data
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        await seed_initial_data(session)

    yield

    # Shutdown: Dispose DB engine
    await engine.dispose()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Agentic AI-Driven Campus Perimeter Security API for Vignan University (VFSTR)",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(access.router)
app.include_router(gates.router)
app.include_router(visitors.router)
app.include_router(alerts.router)
app.include_router(telemetry.router)

# WebSocket Endpoint for Real-Time SOC Dashboards
@app.websocket("/ws/soc")
async def websocket_soc_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keepalive listener
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)

# Serve Frontend Root
@app.get("/")
async def root():
    index_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"status": "ONLINE", "message": "Vignan Smart Access API Operational"}

# Serve logo image
@app.get("/vignan-logo.jpg")
async def get_logo():
    logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "vignan-logo.jpg")
    if os.path.exists(logo_path):
        return FileResponse(logo_path)
    return {"error": "Logo not found"}
