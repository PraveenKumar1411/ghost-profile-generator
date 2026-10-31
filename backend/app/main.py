"""FastAPI application entry point."""

import logging
import logging.config
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.database import lifespan
from app.models.errors import ErrorResponse
from app.routers.router import api_router


def configure_logging() -> None:
    """Configure consistent application logging."""

    settings = get_settings()
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)s "
                    "%(name)s %(message)s",
                },
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                },
            },
            "loggers": {
                "": {
                    "handlers": ["default"],
                    "level": settings.log_level.upper(),
                },
            },
        }
    )


configure_logging()
logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def application_lifespan(app: FastAPI):
    """Initialize and release application resources."""

    async with lifespan(app):
        logger.info("Starting %s", settings.app_name)
        yield
        logger.info("Stopping %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=application_lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Attach a request ID to responses and error logs."""

    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """Return HTTP errors in the standard API shape."""

    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            detail=str(exc.detail),
            request_id=request_id,
        ).model_dump(),
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Return a client-safe validation error response."""

    request_id = getattr(request.state, "request_id", None)
    logger.warning("Request validation failed: %s", exc.errors())
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            detail="Request validation failed",
            request_id=request_id,
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Log unexpected failures without exposing internal details."""

    request_id = getattr(request.state, "request_id", None)
    logger.exception("Unhandled exception, request_id=%s", request_id, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            detail="Internal server error",
            request_id=request_id,
        ).model_dump(),
    )


app.include_router(api_router)


@app.get("/")
async def root() -> dict[str, str]:
    """Return the application status."""

    return {
        "project": "Ghost Profile Generator",
        "status": "running",
        "version": "3.0",
    }
