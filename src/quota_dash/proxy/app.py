from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

import httpx

from quota_dash.proxy.db import init_db, write_api_call
from quota_dash.proxy.handler import resolve_target, build_routes, provider_for_path
from quota_dash.proxy.parser import extract_usage
from quota_dash.proxy.streaming import StreamingBuffer

logger = logging.getLogger(__name__)


def create_proxy_app(
    db_path: Path,
    config_targets: dict[str, str] | None = None,
    target_filter: str | None = None,
    session_tag: str | None = None,
) -> Starlette:
    _routes = build_routes(config_targets)
    _db_path = db_path
    _session_tag = session_tag

    async def startup():
        await init_db(_db_path)

    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "db_path": str(_db_path)})

    async def proxy_handler(request: Request) -> Response:
        path = request.url.path
        target_url = resolve_target(path, _routes)

        if target_url is None:
            return JSONResponse({"error": "No route for path"}, status_code=404)

        # Target filter check
        if target_filter:
            prov = provider_for_path(path)
            if prov and prov != target_filter:
                return JSONResponse(
                    {"error": f"Proxy is configured for {target_filter} only. This path routes to {prov}."},
                    status_code=404,
                )

        body = await request.body()
        fwd_headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "transfer-encoding")}

        try:
            client = httpx.AsyncClient(timeout=120.0)
            req = client.build_request(
                method=request.method,
                url=target_url,
                headers=fwd_headers,
                content=body,
            )
            resp = await client.send(req, stream=True)
        except httpx.HTTPError as e:
            logger.error("Upstream error: %s", e)
            return JSONResponse({"error": "Bad Gateway"}, status_code=502)

        resp_headers = dict(resp.headers)
        is_streaming = "text/event-stream" in resp_headers.get("content-type", "")

        if is_streaming:
            buf = StreamingBuffer()

            async def stream_and_capture():
                try:
                    async for chunk in resp.aiter_text():
                        yield chunk
                        for line in chunk.splitlines():
                            buf.feed_line(line)
                finally:
                    await resp.aclose()
                    await client.aclose()
                    record = buf.extract_usage(resp_headers, endpoint=path, target_url=target_url)
                    record.session_tag = _session_tag
                    try:
                        await write_api_call(_db_path, record)
                    except Exception:
                        logger.exception("Failed to write streaming usage")

            return StreamingResponse(
                stream_and_capture(),
                status_code=resp.status_code,
                headers={k: v for k, v in resp_headers.items() if k.lower() != "transfer-encoding"},
                media_type=resp_headers.get("content-type", "text/event-stream"),
            )
        else:
            resp_body = await resp.aread()
            await resp.aclose()
            await client.aclose()

            try:
                body_json = json.loads(resp_body)
            except (json.JSONDecodeError, ValueError):
                body_json = {}

            record = extract_usage(body_json, resp_headers, endpoint=path, target_url=target_url)
            record.session_tag = _session_tag
            asyncio.create_task(_safe_write(_db_path, record))

            return Response(
                content=resp_body,
                status_code=resp.status_code,
                headers={
                    k: v for k, v in resp_headers.items()
                    if k.lower() not in ("transfer-encoding", "content-encoding")
                },
                media_type=resp_headers.get("content-type"),
            )

    app = Starlette(
        routes=[
            Route("/health", health, methods=["GET"]),
            Route("/{path:path}", proxy_handler, methods=["GET", "POST", "PUT", "DELETE", "PATCH"]),
        ],
        on_startup=[startup],
    )
    return app


async def _safe_write(db_path: Path, record) -> None:
    try:
        await write_api_call(db_path, record)
    except Exception:
        logger.exception("Failed to write usage record")
