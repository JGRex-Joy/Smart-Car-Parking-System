from typing import Literal

import httpx

from app.config import BACKEND_BASE_URL

Gate = Literal["entry", "exit"]

_ENDPOINT_BY_GATE = {
    "entry": "/api/sim/entry",
    "exit": "/api/sim/exit",
}


async def forward_plate_to_backend(gate: Gate, plate_formatted: str) -> dict:
    url = f"{BACKEND_BASE_URL}{_ENDPOINT_BY_GATE[gate]}"
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(url, json={"plate_number": plate_formatted})
        response.raise_for_status()
        return response.json() if response.content else {}
