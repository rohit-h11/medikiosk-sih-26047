import time
import logging
from typing import Callable
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("medikiosk.middleware")

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs every incoming HTTP request details, status code, 
    and execution latency in milliseconds.
    """
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        client_ip = request.client.host if request.client else "unknown"
        
        logger.info(f"--> [REQ] {request.method} {request.url.path} from {client_ip}")
        
        try:
            response = await call_next(request)
            process_time = (time.time() - start_time) * 1000
            response.headers["X-Process-Time-Ms"] = f"{process_time:.2f}"
            
            logger.info(f"<-- [RESP] {request.method} {request.url.path} - Status: {response.status_code} ({process_time:.2f}ms)")
            return response
        except Exception as exc:
            process_time = (time.time() - start_time) * 1000
            logger.error(f"<-- [ERROR] {request.method} {request.url.path} failed after {process_time:.2f}ms: {exc}")
            raise exc

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to inject security headers on every API response.
    """
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

def setup_exception_handlers(app: FastAPI) -> None:
    """
    Registers global exception handlers for uncaught application errors.
    """
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled Exception at {request.url.path}: {str(exc)}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "type": "InternalServerError",
                    "message": "An unexpected error occurred. Please contact system administrator.",
                    "details": str(exc) if app.debug else None
                }
            }
        )
