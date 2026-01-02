"""
FastAPI Backend for Profile Warm-Up UI
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.async_api import async_playwright
from warmup import ProfileWarmUp
from login import login_to_facebook
from config import WARM_UP_CONFIG

app = FastAPI(title="Profile Warm-Up API")

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active connections and sessions
active_connections: List[WebSocket] = []
warmup_sessions = {}


class Profile(BaseModel):
    email: str
    password: str


class WarmupStatus(BaseModel):
    profile: str
    status: str
    action: Optional[str] = None
    stats: Optional[dict] = None


async def broadcast_message(message: dict):
    """Send message to all connected clients"""
    for connection in active_connections:
        try:
            await connection.send_json(message)
        except:
            pass


@app.get("/")
async def root():
    return {"status": "running", "service": "Profile Warm-Up API"}


@app.get("/config")
async def get_config():
    return WARM_UP_CONFIG


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Handle incoming messages if needed
    except WebSocketDisconnect:
        active_connections.remove(websocket)


@app.post("/warmup/start")
async def start_warmup(profile: Profile):
    """Start warm-up for a single profile"""

    async def run_warmup_task():
        await broadcast_message({
            "type": "status",
            "profile": profile.email,
            "status": "starting",
            "message": "🚀 Launching browser..."
        })

        try:
            async with async_playwright() as p:
                # Launch browser with STEALTH settings
                # Using Firefox as it works better on macOS
                browser = await p.firefox.launch(
                    headless=False,
                    args=['--start-maximized']
                )

                await broadcast_message({
                    "type": "status",
                    "profile": profile.email,
                    "status": "browser_ready",
                    "message": "🌐 Browser launched (stealth mode)!"
                })

                # Create context with realistic settings
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0',
                    locale='en-US',
                    timezone_id='America/New_York',
                )

                page = await context.new_page()

                # Login
                await broadcast_message({
                    "type": "status",
                    "profile": profile.email,
                    "status": "logging_in",
                    "message": "🔐 Logging in..."
                })

                login_success = await login_to_facebook(page, profile.email, profile.password)

                if not login_success:
                    await broadcast_message({
                        "type": "error",
                        "profile": profile.email,
                        "status": "login_failed",
                        "message": "❌ Login failed!"
                    })
                    await browser.close()
                    return

                await broadcast_message({
                    "type": "status",
                    "profile": profile.email,
                    "status": "logged_in",
                    "message": "✅ Login successful!"
                })

                # Run warm-up
                await broadcast_message({
                    "type": "status",
                    "profile": profile.email,
                    "status": "warming_up",
                    "message": "🔥 Starting warm-up..."
                })

                warmup = ProfileWarmUp(page, profile.email.split('@')[0])

                # Custom run with broadcasts
                if WARM_UP_CONFIG['enabled']:
                    stats = await warmup.run()

                    await broadcast_message({
                        "type": "complete",
                        "profile": profile.email,
                        "status": "completed",
                        "message": "🎉 Warm-up complete!",
                        "stats": stats
                    })

                await browser.close()

        except Exception as e:
            await broadcast_message({
                "type": "error",
                "profile": profile.email,
                "status": "error",
                "message": f"❌ Error: {str(e)}"
            })

    # Run in background
    asyncio.create_task(run_warmup_task())

    return {"status": "started", "profile": profile.email}


@app.post("/warmup/stop/{email}")
async def stop_warmup(email: str):
    """Stop warm-up for a profile"""
    # TODO: Implement stop functionality
    return {"status": "stopping", "profile": email}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
