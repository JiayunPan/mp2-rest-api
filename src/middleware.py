import logging
import time
import uuid

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


async def log_requests(request: Request, call_next):
    """Log one request and attach its request ID to the response."""
    request_id = uuid.uuid4().hex[:8]
    request.state.request_id = request_id
    started = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        # TODO 1：未预料的异常，记 ERROR 并带上完整 traceback，但不把细节暴露给客户端
        logger.error(
            "request_id=%s unhandled exception during %s %s",
            request_id, request.method, request.url.path,
            exc_info=True,
        )
        response = JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    duration_ms = (time.perf_counter() - started) * 1000

    # TODO 2：拼一条含 request_id、方法、路径、状态码、耗时的消息
    message = (
        "request_id=%s %s %s status=%d duration=%.1fms"
        % (
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
    )

    # TODO 3：按状态码分级——5xx 用 ERROR，4xx 用 WARNING，其余 INFO
    if response.status_code >= 500:
        logger.error(message)
    elif response.status_code >= 400:
        logger.warning(message)
    else:
        logger.info(message)

    response.headers["X-Request-ID"] = request_id
    return response