import os

BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://localhost:8000")

MAX_CORRECTIONS_TO_TRUST = int(os.getenv("MAX_CORRECTIONS_TO_TRUST", "2"))
