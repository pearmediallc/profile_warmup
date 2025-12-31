"""
Start the backend server
Run: python start_backend.py
"""

import subprocess
import sys
import os

# Change to project directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

print("=" * 50)
print("🚀 Starting Backend Server")
print("=" * 50)

# Install requirements
print("\n📦 Installing dependencies...")
subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                "fastapi", "uvicorn", "websockets", "pydantic", "playwright"])

# Run server
print("\n🌐 Starting server at http://localhost:8000")
print("Press Ctrl+C to stop\n")

os.chdir("backend")
subprocess.run([sys.executable, "-m", "uvicorn", "server:app", "--reload", "--host", "0.0.0.0", "--port", "8000"])
