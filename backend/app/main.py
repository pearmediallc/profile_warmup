"""
FastAPI Backend for Profile Warm-Up - Production Ready
"""

import os
import logging
import glob
import json
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import redis

from app.celery_app import celery_app
from app.tasks import warmup_profile_task, SCREENSHOTS_DIR, screenshot_to_base64, CLOUDINARY_CONFIGURED
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

# Redis pub/sub for status broadcasting
pubsub_client = None
if REDIS_AVAILABLE:
    try:
        pubsub_client = redis.from_url(REDIS_URL)
    except Exception:
        pass


# Background task for Redis pub/sub subscriber
async def redis_subscriber():
    """Subscribe to Redis channel and broadcast to WebSocket clients"""
    if not pubsub_client:
        logger.warning("Redis pub/sub not available")
        return

    pubsub = pubsub_client.pubsub()
    pubsub.subscribe("warmup_status")
    logger.info("Started Redis pub/sub subscriber")

    while True:
        try:
            message = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                data = json.loads(message["data"])
                logger.debug(f"Broadcasting status: {data.get('status')}")

                # Broadcast to all connected WebSocket clients
                for connection in active_connections[:]:  # Use slice copy to avoid modification during iteration
                    try:
                        await connection.send_json(data)
                    except Exception:
                        # Remove dead connections
                        try:
                            active_connections.remove(connection)
                        except ValueError:
                            pass

            await asyncio.sleep(0.1)  # Small delay to prevent busy loop

        except Exception as e:
            logger.error(f"Redis subscriber error: {e}")
            await asyncio.sleep(5)  # Wait before retry


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Start Redis subscriber in background
    subscriber_task = None
    if REDIS_AVAILABLE:
        subscriber_task = asyncio.create_task(redis_subscriber())
        logger.info("Redis subscriber started")

    yield

    # Cleanup on shutdown
    if subscriber_task:
        subscriber_task.cancel()
        try:
            await subscriber_task
        except asyncio.CancelledError:
            pass
    browser_pool.cleanup_all()
    logger.info("Shutdown complete")


# FastAPI app
app = FastAPI(
    title="Profile Warm-Up API",
    description="Production-ready Facebook profile warming service",
    version="2.0.0",
    lifespan=lifespan
)

# CORS - Build origins list dynamically
cors_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8000",
]

# Add frontend URL from environment (with correct default)
frontend_url = os.getenv("FRONTEND_URL", "https://profile-warmup-frontend.onrender.com")
if frontend_url:
    cors_origins.append(frontend_url)

# Also allow any onrender.com subdomain for flexibility
cors_origins.append("https://*.onrender.com")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"https://.*\.onrender\.com",  # Regex for all Render subdomains
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


# Static files directory (for combined frontend+backend deployment)
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
FRONTEND_AVAILABLE = os.path.exists(STATIC_DIR) and os.path.exists(os.path.join(STATIC_DIR, "index.html"))

if FRONTEND_AVAILABLE:
    # Mount static assets (js, css, etc.)
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")
    logger.info(f"Frontend static files mounted from {STATIC_DIR}")


@app.get("/")
async def root():
    """Root endpoint - serves frontend if available, otherwise API info"""
    if FRONTEND_AVAILABLE:
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
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
        "cloudinary": CLOUDINARY_CONFIGURED,
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
    # Add backend directory to path (parent of app/)
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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


@app.get("/screenshots/{email}")
async def list_screenshots(email: str):
    """
    List all screenshots for a profile
    Returns list of screenshot info with timestamps
    """
    safe_email = email.split('@')[0].replace('.', '_')
    pattern = os.path.join(SCREENSHOTS_DIR, f"{safe_email}_*.png")
    files = glob.glob(pattern)

    screenshots = []
    for filepath in sorted(files, key=os.path.getmtime, reverse=True):
        filename = os.path.basename(filepath)
        stat = os.stat(filepath)
        screenshots.append({
            "filename": filename,
            "path": filepath,
            "size_bytes": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "stage": filename.split('_')[1] if '_' in filename else "unknown"
        })

    return {
        "email": email,
        "screenshot_count": len(screenshots),
        "screenshots": screenshots
    }


@app.get("/screenshots/{email}/{filename}")
async def get_screenshot(email: str, filename: str, format: str = "file"):
    """
    Get a specific screenshot
    format=file: Return as file download
    format=base64: Return as base64 encoded string
    """
    safe_email = email.split('@')[0].replace('.', '_')

    # Security: Ensure filename belongs to this email
    if not filename.startswith(safe_email):
        raise HTTPException(status_code=403, detail="Access denied to this screenshot")

    filepath = os.path.join(SCREENSHOTS_DIR, filename)

    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Screenshot not found")

    if format == "base64":
        base64_data = screenshot_to_base64(filepath)
        if base64_data:
            return {
                "filename": filename,
                "format": "base64",
                "data": base64_data
            }
        raise HTTPException(status_code=500, detail="Failed to encode screenshot")

    return FileResponse(filepath, media_type="image/png", filename=filename)


@app.get("/screenshots/{email}/latest")
async def get_latest_screenshot(email: str):
    """Get the most recent screenshot for a profile"""
    safe_email = email.split('@')[0].replace('.', '_')
    pattern = os.path.join(SCREENSHOTS_DIR, f"{safe_email}_*.png")
    files = glob.glob(pattern)

    if not files:
        raise HTTPException(status_code=404, detail="No screenshots found for this profile")

    # Get most recent file
    latest = max(files, key=os.path.getmtime)
    filename = os.path.basename(latest)
    base64_data = screenshot_to_base64(latest)

    return {
        "filename": filename,
        "stage": filename.split('_')[1] if '_' in filename else "unknown",
        "format": "base64",
        "data": base64_data
    }


@app.delete("/screenshots/{email}")
async def delete_screenshots(email: str):
    """Delete all screenshots for a profile"""
    safe_email = email.split('@')[0].replace('.', '_')
    pattern = os.path.join(SCREENSHOTS_DIR, f"{safe_email}_*.png")
    files = glob.glob(pattern)

    deleted = 0
    for filepath in files:
        try:
            os.remove(filepath)
            deleted += 1
        except Exception as e:
            logger.error(f"Failed to delete {filepath}: {e}")

    return {
        "email": email,
        "deleted_count": deleted
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
