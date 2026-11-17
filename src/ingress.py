"""Apply body, time and admission bounds before FastAPI parses multipart uploads."""

import asyncio
import time
from fastapi import HTTPException
from starlette.responses import JSONResponse
from src.config import settings


class IngressMiddleware:
    def __init__(self, app):
        self.app = app
        self.active = 0

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] not in ("/parse", "/parse-batch"):
            return await self.app(scope, receive, send)
        if self.active >= settings.max_active_parses:
            return await JSONResponse({"error": "Parser busy; retry later"}, 503,
                                      headers={"Retry-After": "2"})(scope, receive, send)
        batch = scope["path"] == "/parse-batch"
        limit = min(settings.max_request_bytes,
                    settings.max_upload_bytes * (settings.batch_max_size if batch else 1) + 65536)
        headers = dict(scope.get("headers", []))
        try:
            declared = int(headers.get(b"content-length", b"0"))
        except ValueError:
            declared = -1
        if declared < 0 or declared > limit:
            return await JSONResponse({"error": "Request exceeds upload limit"}, 413)(scope, receive, send)
        started = time.monotonic()
        scope.setdefault("state", {})["parse_deadline"] = started + (
            settings.batch_deadline_seconds if batch else settings.parse_deadline_seconds)
        ingress_deadline = min(started + settings.ingress_timeout_seconds,
                               scope["state"]["parse_deadline"])
        received = 0
        response_started = False

        async def bounded_receive():
            nonlocal received
            remaining = ingress_deadline - time.monotonic()
            if remaining <= 0:
                raise HTTPException(408, "Upload deadline exceeded")
            try:
                message = await asyncio.wait_for(receive(), remaining)
            except TimeoutError as exc:
                raise HTTPException(408, "Upload deadline exceeded") from exc
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise HTTPException(413, "Request exceeds upload limit")
            return message

        async def tracked_send(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        self.active += 1
        try:
            # Bounds multipart parsing itself; route-level bounds handle model work.
            await self.app(scope, bounded_receive, tracked_send)
        except HTTPException as exc:
            if response_started:
                raise
            await JSONResponse({"error": exc.detail}, exc.status_code)(scope, receive, send)
        finally:
            self.active -= 1
