"""
FastAPI Backend for Profile Warm-Up - Production Ready
WITH COMPREHENSIVE LOGGING FOR DEBUGGING
"""

import os
import sys
import logging
import glob
import json
import asyncio
import traceback
from typing import List, Optional, Dict, Any
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import redis

# ============================================================
# COMPREHENSIVE LOGGING SETUP
# ============================================================
print("=" * 60, flush=True)
print("STARTING PROFILE WARMUP API", flush=True)
print(f"Python version: {sys.version}", flush=True)
print(f"Working directory: {os.getcwd()}", flush=True)
print("=" * 60, flush=True)

logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for more detail
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)  # Explicitly use stdout
    ]
)
logger = logging.getLogger(__name__)
logger.info("Logger initialized")

# ============================================================
# IMPORT APP MODULES WITH ERROR HANDLING
# ============================================================
print("[STARTUP] Importing app modules...", flush=True)
try:
    from app.tasks import warmup_profile_task, SCREENSHOTS_DIR, screenshot_to_base64, CLOUDINARY_CONFIGURED, set_status_callback
    print("[STARTUP] ✓ tasks module imported", flush=True)
except Exception as e:
    print(f"[STARTUP] ✗ Failed to import tasks: {e}", flush=True)
    traceback.print_exc()
    raise

try:
    from app.playwright_browser import browser_pool
    print("[STARTUP] ✓ playwright_browser module imported", flush=True)
except Exception as e:
    print(f"[STARTUP] ✗ Failed to import playwright_browser: {e}", flush=True)
    traceback.print_exc()
    raise

# ============================================================
# REDIS CONNECTION
# ============================================================
print("[STARTUP] Connecting to Redis...", flush=True)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
try:
    redis_client = redis.from_url(REDIS_URL)
    redis_client.ping()
    REDIS_AVAILABLE = True
    print(f"[STARTUP] ✓ Redis connected: {REDIS_URL[:30]}...", flush=True)
    logger.info("Redis connected")
except Exception as e:
    print(f"[STARTUP] ✗ Redis not available: {e}", flush=True)
    logger.warning(f"Redis not available: {e}")
    REDIS_AVAILABLE = False
    redis_client = None

# Redis pub/sub for status broadcasting
pubsub_client = None
if REDIS_AVAILABLE:
    try:
        pubsub_client = redis.from_url(REDIS_URL)
        print("[STARTUP] ✓ Redis pub/sub client created", flush=True)
    except Exception as e:
        print(f"[STARTUP] ✗ Redis pub/sub failed: {e}", flush=True)


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
                for connection in active_connections[:]:
                    try:
                        await connection.send_json(data)
                    except Exception:
                        try:
                            active_connections.remove(connection)
                        except ValueError:
                            pass

            await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Redis subscriber error: {e}")
            await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    print("[LIFESPAN] Application starting...", flush=True)

    # Start Redis subscriber in background
    subscriber_task = None
    if REDIS_AVAILABLE:
        subscriber_task = asyncio.create_task(redis_subscriber())
        print("[LIFESPAN] ✓ Redis subscriber started", flush=True)
        logger.info("Redis subscriber started")

    print("[LIFESPAN] ✓ Application ready to serve requests", flush=True)
    yield

    # Cleanup on shutdown
    print("[LIFESPAN] Application shutting down...", flush=True)
    if subscriber_task:
        subscriber_task.cancel()
        try:
            await subscriber_task
        except asyncio.CancelledError:
            pass
    browser_pool.cleanup_all()
    print("[LIFESPAN] ✓ Shutdown complete", flush=True)
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

frontend_url = os.getenv("FRONTEND_URL", "https://profile-warmup-frontend.onrender.com")
if frontend_url:
    cors_origins.append(frontend_url)

cors_origins.append("https://*.onrender.com")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"https://.*\.onrender\.com",
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


# Static files directory
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
FRONTEND_AVAILABLE = os.path.exists(STATIC_DIR) and os.path.exists(os.path.join(STATIC_DIR, "index.html"))

if FRONTEND_AVAILABLE:
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")
    print(f"[STARTUP] ✓ Frontend static files mounted from {STATIC_DIR}", flush=True)
    logger.info(f"Frontend static files mounted from {STATIC_DIR}")
else:
    print(f"[STARTUP] ✗ No frontend found at {STATIC_DIR}", flush=True)


# ============================================================
# DEBUG ENDPOINT - Check browser installation
# ============================================================
@app.get("/debug/browser")
async def debug_browser():
    """Debug endpoint to test Playwright browser installation"""
    import subprocess

    print("[DEBUG] /debug/browser called", flush=True)
    browser_path = os.environ.get('PLAYWRIGHT_BROWSERS_PATH', '/app/.playwright-browsers')
    result = {
        "code_version": "2024-01-12-v8-fixed-browser-path",
        "python_version": sys.version,
        "cwd": os.getcwd(),
        "playwright_version": None,
        "playwright_browsers_path": browser_path,
        "chromium_paths": [],
        "env_render": os.environ.get("RENDER", "not set"),
        "error": None
    }

    try:
        # Check playwright version
        pw_result = subprocess.run(['playwright', '--version'], capture_output=True, text=True, timeout=10)
        result["playwright_version"] = pw_result.stdout.strip() if pw_result.stdout else pw_result.stderr.strip()
        print(f"[DEBUG] Playwright version: {result['playwright_version']}", flush=True)

        # Try to find chromium in the configured location
        search_paths = [browser_path, '/app/.playwright-browsers', '/root/.cache/ms-playwright']
        for search_path in search_paths:
            if os.path.exists(search_path):
                find_result = subprocess.run(
                    ['find', search_path, '-name', 'chrome', '-type', 'f'],
                    capture_output=True, text=True, timeout=30
                )
                if find_result.stdout:
                    result["chromium_paths"] = find_result.stdout.strip().split('\n')[:5]
                    result["browser_found_in"] = search_path
                    break
        print(f"[DEBUG] Chromium paths: {result['chromium_paths']}", flush=True)

    except Exception as e:
        result["error"] = str(e)
        print(f"[DEBUG] Error: {e}", flush=True)

    return result


@app.get("/debug/test-browser")
async def test_browser_launch():
    """
    Actually try to launch browser and return detailed diagnostic info.
    Uses ASYNC Playwright API since we're in an async context.
    """
    import subprocess
    from playwright.async_api import async_playwright

    browser_path = os.environ.get('PLAYWRIGHT_BROWSERS_PATH', '/app/.playwright-browsers')
    result = {
        "code_version": "2024-01-12-v8-fixed-browser-path",
        "playwright_browsers_path": browser_path,
        "steps": [],
        "success": False,
        "error": None,
        "error_type": None,
        "browser_launched": False,
        "page_created": False,
        "navigation_test": None
    }

    playwright = None
    browser = None
    page = None

    try:
        # Step 1: Check Playwright version
        result["steps"].append("1. Checking Playwright version...")
        try:
            pw_result = subprocess.run(['playwright', '--version'], capture_output=True, text=True, timeout=10)
            result["playwright_version"] = pw_result.stdout.strip() if pw_result.stdout else pw_result.stderr.strip()
            result["steps"].append(f"   ✓ Playwright: {result['playwright_version']}")
        except Exception as e:
            result["steps"].append(f"   ✗ Version check failed: {e}")

        # Step 2: Find Chromium (check multiple locations)
        result["steps"].append("2. Looking for Chromium executable...")
        result["steps"].append(f"   PLAYWRIGHT_BROWSERS_PATH = {browser_path}")
        try:
            # Check configured path first, then fallbacks
            search_paths = [browser_path, '/app/.playwright-browsers', '/root/.cache/ms-playwright']
            found = False
            for search_path in search_paths:
                if not os.path.exists(search_path):
                    result["steps"].append(f"   Path {search_path} does not exist")
                    continue

                find_result = subprocess.run(
                    ['find', search_path, '-name', 'chrome', '-type', 'f'],
                    capture_output=True, text=True, timeout=30
                )
                if find_result.stdout:
                    paths = find_result.stdout.strip().split('\n')[:3]
                    result["chromium_paths"] = paths
                    result["browser_found_in"] = search_path
                    result["steps"].append(f"   ✓ Found in {search_path}: {paths[0] if paths else 'none'}")
                    found = True
                    break
                else:
                    result["steps"].append(f"   No chrome in {search_path}")

            if not found:
                result["steps"].append("   ✗ Chrome NOT found in any expected location!")
        except Exception as e:
            result["steps"].append(f"   ✗ Search failed: {e}")

        # Step 3: Start Playwright (ASYNC API)
        result["steps"].append("3. Starting Playwright async_playwright()...")
        playwright = await async_playwright().start()
        result["steps"].append("   ✓ Playwright started")

        # Step 4: Launch browser
        result["steps"].append("4. Launching Chromium browser...")
        browser_args = [
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--disable-extensions',
        ]
        browser = await playwright.chromium.launch(
            headless=True,
            args=browser_args
        )
        result["browser_launched"] = True
        result["steps"].append("   ✓ Browser launched!")

        # Step 5: Create page
        result["steps"].append("5. Creating new page...")
        page = await browser.new_page(
            viewport={'width': 1280, 'height': 720}
        )
        result["page_created"] = True
        result["steps"].append("   ✓ Page created!")

        # Step 6: Navigate to test page
        result["steps"].append("6. Testing navigation to example.com...")
        await page.goto("https://example.com", timeout=30000)
        result["navigation_test"] = {
            "url": page.url,
            "title": await page.title()
        }
        result["steps"].append(f"   ✓ Navigated! Title: {result['navigation_test']['title']}")

        result["success"] = True
        result["steps"].append("=== ALL TESTS PASSED ===")

    except Exception as e:
        result["error"] = str(e)
        result["error_type"] = type(e).__name__
        result["steps"].append(f"   ✗ ERROR: {type(e).__name__}: {e}")
        import traceback
        result["traceback"] = traceback.format_exc()

    finally:
        # Cleanup
        result["steps"].append("7. Cleaning up...")
        try:
            if page:
                await page.close()
                result["steps"].append("   ✓ Page closed")
            if browser:
                await browser.close()
                result["steps"].append("   ✓ Browser closed")
            if playwright:
                await playwright.stop()
                result["steps"].append("   ✓ Playwright stopped")
        except Exception as e:
            result["steps"].append(f"   Cleanup error: {e}")

    return result


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
        "active_tasks": len(active_tasks),
        "code_version": "2024-01-12-v8-fixed-browser-path",
        "playwright_browsers_path": os.environ.get('PLAYWRIGHT_BROWSERS_PATH', '/app/.playwright-browsers')
    }

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
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config import WARM_UP_CONFIG
    return WARM_UP_CONFIG


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates"""
    await websocket.accept()
    active_connections.append(websocket)
    print(f"[WS] WebSocket connected. Total: {len(active_connections)}", flush=True)
    logger.info(f"WebSocket connected. Total: {len(active_connections)}")

    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.remove(websocket)
        print(f"[WS] WebSocket disconnected. Total: {len(active_connections)}", flush=True)
        logger.info(f"WebSocket disconnected. Total: {len(active_connections)}")


@app.post("/warmup/start", response_model=WarmupResponse)
async def start_warmup(profile: Profile, background_tasks: BackgroundTasks):
    """Start warm-up for a profile"""
    email = profile.email

    print("=" * 60, flush=True)
    print(f"[WARMUP] /warmup/start called for: {email}", flush=True)
    print("=" * 60, flush=True)
    logger.info(f"[WARMUP] Received warmup request for {email}")

    # Check if already running
    if email in active_tasks and active_tasks[email].get("status") == "running":
        print(f"[WARMUP] ✗ Already running for {email}", flush=True)
        raise HTTPException(status_code=400, detail="Warmup already running for this profile")

    try:
        active_tasks[email] = {
            "status": "running",
            "started_at": datetime.utcnow().isoformat()
        }
        print(f"[WARMUP] Task registered for {email}", flush=True)

        # Run in background
        print(f"[WARMUP] Adding background task for {email}", flush=True)
        background_tasks.add_task(run_warmup_direct, email, profile.password)
        print(f"[WARMUP] ✓ Background task added for {email}", flush=True)

        await broadcast_message({
            "type": "status",
            "profile": email,
            "status": "starting",
            "message": "🚀 Starting warmup..."
        })

        return WarmupResponse(
            status="started",
            profile=email,
            message="Warmup started"
        )

    except Exception as e:
        print(f"[WARMUP] ✗ Failed to start warmup: {e}", flush=True)
        traceback.print_exc()
        logger.error(f"Failed to start warmup: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def run_warmup_direct(email: str, password: str):
    """Run warmup in background thread"""
    print("=" * 60, flush=True)
    print(f"[WARMUP-BG] Background task STARTED for {email}", flush=True)
    print("=" * 60, flush=True)

    try:
        # Set up callback for status updates via WebSocket
        print(f"[WARMUP-BG] Setting up status callback for {email}", flush=True)
        set_status_callback(email, lambda data: asyncio.create_task(broadcast_message(data)))

        # Run the task in a thread pool to not block the event loop
        print(f"[WARMUP-BG] Getting event loop...", flush=True)
        loop = asyncio.get_event_loop()

        print(f"[WARMUP-BG] Calling warmup_profile_task in executor...", flush=True)
        result = await loop.run_in_executor(
            None,
            lambda: warmup_profile_task(email, password)
        )
        print(f"[WARMUP-BG] warmup_profile_task completed. Result: {result}", flush=True)

        # Check if warmup actually succeeded or had an error
        if result.get("status") == "error" or result.get("status") == "login_failed":
            error_msg = result.get("error", "Unknown error")
            print(f"[WARMUP-BG] ✗ Warmup failed with status: {result.get('status')}", flush=True)
            await broadcast_message({
                "type": "error",
                "profile": email,
                "status": result.get("status"),
                "message": f"❌ Warmup failed: {error_msg}",
                "stats": result
            })
        else:
            await broadcast_message({
                "type": "complete",
                "profile": email,
                "status": "completed",
                "message": "🎉 Warmup complete!",
                "stats": result
            })

    except Exception as e:
        print(f"[WARMUP-BG] ✗ ERROR in background task: {e}", flush=True)
        traceback.print_exc()
        logger.error(f"Warmup error: {e}")
        await broadcast_message({
            "type": "error",
            "profile": email,
            "status": "error",
            "message": f"❌ Error: {str(e)}"
        })

    finally:
        print(f"[WARMUP-BG] Cleaning up for {email}", flush=True)
        set_status_callback(email, None)
        if email in active_tasks:
            del active_tasks[email]
        print(f"[WARMUP-BG] Background task FINISHED for {email}", flush=True)


@app.get("/warmup/status/{email}")
async def get_warmup_status(email: str):
    """Get status of a warmup task"""
    if email not in active_tasks:
        return {"status": "not_found", "profile": email}
    task_info = active_tasks[email]
    return {"status": task_info.get("status", "unknown"), "profile": email}


@app.post("/warmup/stop/{email}")
async def stop_warmup(email: str):
    """Stop a running warmup task"""
    if email not in active_tasks:
        raise HTTPException(status_code=404, detail="No active warmup for this profile")

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
    """List all screenshots for a profile"""
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
    """Get a specific screenshot"""
    safe_email = email.split('@')[0].replace('.', '_')

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


print("[STARTUP] ✓ All routes registered", flush=True)
print("[STARTUP] ✓ Application module loaded successfully", flush=True)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
