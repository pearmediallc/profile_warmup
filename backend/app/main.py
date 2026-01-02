"""
FastAPI Backend for Profile Warm-Up - Production Ready
"""

import os
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import redis

from app.celery_app import celery_app
from app.tasks import warmup_profile_task
from app.browser import browser_pool

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Redis connection
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
try:
    redis_client = redis.from_url(REDIS_URL)
    redis_client.ping()
    REDIS_AVAILABLE = True
    logger.info("Redis connected")
except Exception as e:
    logger.warning(f"Redis not available: {e}")
    REDIS_AVAILABLE = False
    redis_client = None

# FastAPI app
app = FastAPI(
    title="Profile Warm-Up API",
    description="Production-ready Facebook profile warming service",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        os.getenv("FRONTEND_URL", "https://profile-warmup.onrender.com")
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connections
active_connections: List[WebSocket] = []

# Task tracking
active_tasks: Dict[str, Dict[str, Any]] = {}


class Profile(BaseModel):
    email: str
    password: str


class WarmupResponse(BaseModel):
    status: str
    profile: str
    task_id: Optional[str] = None
    message: Optional[str] = None


async def broadcast_message(message: dict):
    """Send message to all connected WebSocket clients"""
    for connection in active_connections:
        try:
            await connection.send_json(message)
        except Exception:
            pass


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "status": "running",
        "service": "Profile Warm-Up API",
        "version": "2.0.0",
        "redis": REDIS_AVAILABLE
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker/Render"""
    health = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "redis": REDIS_AVAILABLE,
        "active_browsers": len(browser_pool.active_browsers),
        "active_tasks": len(active_tasks)
    }

    # Check Redis
    if redis_client:
        try:
            redis_client.ping()
            health["redis_ping"] = "ok"
        except Exception:
            health["redis_ping"] = "failed"
            health["status"] = "degraded"

    return health


@app.get("/config")
async def get_config():
    """Get warmup configuration"""
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from config import WARM_UP_CONFIG
    return WARM_UP_CONFIG


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates"""
    await websocket.accept()
    active_connections.append(websocket)
    logger.info(f"WebSocket connected. Total: {len(active_connections)}")

    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming messages if needed
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(active_connections)}")


@app.post("/warmup/start", response_model=WarmupResponse)
async def start_warmup(profile: Profile, background_tasks: BackgroundTasks):
    """
    Start warm-up for a profile
    Uses Celery if Redis available, otherwise runs in background
    """
    email = profile.email

    # Check if already running
    if email in active_tasks and active_tasks[email].get("status") == "running":
        raise HTTPException(status_code=400, detail="Warmup already running for this profile")

    try:
        if REDIS_AVAILABLE:
            # Use Celery for production
            task = warmup_profile_task.delay(email, profile.password)
            task_id = task.id

            active_tasks[email] = {
                "task_id": task_id,
                "status": "running",
                "started_at": datetime.utcnow().isoformat()
            }

            logger.info(f"Warmup task started via Celery: {task_id}")

            # Broadcast status
            await broadcast_message({
                "type": "status",
                "profile": email,
                "status": "starting",
                "message": "🚀 Warmup task queued...",
                "task_id": task_id
            })

            return WarmupResponse(
                status="started",
                profile=email,
                task_id=task_id,
                message="Warmup queued via Celery"
            )

        else:
            # Fallback: run directly (not recommended for production)
            logger.warning("Redis not available, running warmup directly")

            active_tasks[email] = {
                "status": "running",
                "started_at": datetime.utcnow().isoformat()
            }

            # Run in background (simplified version)
            background_tasks.add_task(run_warmup_direct, email, profile.password)

            await broadcast_message({
                "type": "status",
                "profile": email,
                "status": "starting",
                "message": "🚀 Starting warmup (direct mode)..."
            })

            return WarmupResponse(
                status="started",
                profile=email,
                message="Warmup started directly (Redis not available)"
            )

    except Exception as e:
        logger.error(f"Failed to start warmup: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def run_warmup_direct(email: str, password: str):
    """
    Run warmup directly without Celery
    Fallback for when Redis is not available
    """
    from app.tasks import warmup_profile_task

    try:
        # Run synchronously
        result = warmup_profile_task(email, password)

        await broadcast_message({
            "type": "complete",
            "profile": email,
            "status": "completed",
            "message": "🎉 Warmup complete!",
            "stats": result
        })

    except Exception as e:
        await broadcast_message({
            "type": "error",
            "profile": email,
            "status": "error",
            "message": f"❌ Error: {str(e)}"
        })

    finally:
        if email in active_tasks:
            del active_tasks[email]


@app.get("/warmup/status/{email}")
async def get_warmup_status(email: str):
    """Get status of a warmup task"""
    if email not in active_tasks:
        return {"status": "not_found", "profile": email}

    task_info = active_tasks[email]

    if REDIS_AVAILABLE and "task_id" in task_info:
        from celery.result import AsyncResult
        result = AsyncResult(task_info["task_id"], app=celery_app)

        return {
            "status": result.status,
            "profile": email,
            "task_id": task_info["task_id"],
            "result": result.result if result.ready() else None
        }

    return {"status": task_info.get("status", "unknown"), "profile": email}


@app.post("/warmup/stop/{email}")
async def stop_warmup(email: str):
    """Stop a running warmup task"""
    if email not in active_tasks:
        raise HTTPException(status_code=404, detail="No active warmup for this profile")

    task_info = active_tasks[email]

    if REDIS_AVAILABLE and "task_id" in task_info:
        celery_app.control.revoke(task_info["task_id"], terminate=True)

    # Cleanup browsers
    browser_pool.cleanup_all()

    del active_tasks[email]

    await broadcast_message({
        "type": "status",
        "profile": email,
        "status": "stopped",
        "message": "⏹️ Warmup stopped"
    })

    return {"status": "stopped", "profile": email}


@app.get("/tasks")
async def list_tasks():
    """List all active tasks"""
    return {
        "active_tasks": active_tasks,
        "active_browsers": len(browser_pool.active_browsers),
        "websocket_connections": len(active_connections)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
