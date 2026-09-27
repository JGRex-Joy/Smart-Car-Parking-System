"""
    PARKING_BASE_URL=http://192.168.1.50:8000 uvicorn app.main:app --host 0.0.0.0
"""
import os

BASE_URL = os.getenv("PARKING_BASE_URL", "http://localhost:8000")
