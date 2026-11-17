"""Cancellable backend HTTP with a wall-clock budget as well as socket timeouts."""

import asyncio
import httpx


async def post_json(url: str, payload: dict, timeout: float) -> dict:
    async with asyncio.timeout(timeout):
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()


async def get_json(url: str, timeout: float = 5) -> dict:
    async with asyncio.timeout(timeout):
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()


def model_available(configured: str, names: list[str]) -> bool:
    def normalized(name):
        # A bare model name means :latest, never any tag in the family.
        return name if ":" in name.rsplit("/", 1)[-1] else name + ":latest"
    return normalized(configured) in {normalized(name) for name in names if isinstance(name, str)}


def require_complete(body: dict):
    if body.get("done_reason") in ("length", "max_tokens") or body.get("done") is False:
        raise ValueError("Model output incomplete: output token limit reached")
