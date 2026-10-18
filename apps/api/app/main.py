from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.routers import agent, auth, chat, conversations, documents, features, health, models, providers
from app.services.credentials import install_log_redaction
from app.services.agent import recover_interrupted_tasks

settings = get_settings()

class SecurityHeaders:
    """Pure ASGI middleware (does not interfere with streaming or client disconnects)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def wrapped(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.setdefault("X-Content-Type-Options", "nosniff")
                headers.setdefault("Referrer-Policy", "no-referrer")
                headers.setdefault("X-Frame-Options", "DENY")
                if scope["path"].startswith(("/api/v1/providers", "/api/v1/auth")):
                    headers.setdefault("Cache-Control", "no-store")
            await send(message)

        await self.app(scope, receive, wrapped)


@asynccontextmanager
async def lifespan(_: FastAPI):
    install_log_redaction()
    recover_interrupted_tasks()
    yield


app = FastAPI(title="SYNAPTO API", version=settings.version, lifespan=lifespan)

app.add_middleware(SecurityHeaders)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)

for r in (health.router, auth.router, conversations.router, documents.router, chat.router, models.router, features.router, agent.router, providers.router):
    app.include_router(r, prefix="/api/v1")


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


@app.exception_handler(StarletteHTTPException)  # also covers FastAPI HTTPException, 404 and 405
async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
    return _error(exc.status_code, "http_error", str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    return _error(422, "validation_error", "Request validation failed")


@app.exception_handler(Exception)
async def unhandled_error(_: Request, __: Exception) -> JSONResponse:
    return _error(500, "internal_error", "Unexpected server error")
