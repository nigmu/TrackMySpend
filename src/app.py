import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .core.config import FRONTEND_ORIGIN
from .core.logging import RequestLogMiddleware, configure_logging, get_logger

os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
configure_logging()
logger = get_logger(__name__)

from .accounts.routes import router as accounts_router
from .companion.routes import RELEASES_DIR
from .companion.routes import router as companion_router
from .filters.routes import router as filters_router
from .ingestion.routes import router as ingestion_router
from .logs.routes import router as logs_router
from .parsing.routes import router as parsing_router
from .scheduler import poller_loop
from .sms.routes import router as sms_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("SERVER_STARTUP")
    RELEASES_DIR.mkdir(parents=True, exist_ok=True)
    task = asyncio.create_task(poller_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    logger.info("SERVER_SHUTDOWN")


app = FastAPI(
    title="TrackMySpend",
    description="Personal finance tracker API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(RequestLogMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        FRONTEND_ORIGIN,
        "http://localhost:2007",
        "http://127.0.0.1:2007",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(accounts_router)
app.include_router(filters_router)
app.include_router(ingestion_router)
app.include_router(parsing_router)
app.include_router(sms_router)
app.include_router(logs_router)
app.include_router(companion_router)

RELEASES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/releases", StaticFiles(directory=RELEASES_DIR), name="releases")


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    if request.url.path == "/sms/ingest":
        logger.warning("sms ingest validation failed errors=%s", exc.errors())
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.get("/")
def root():
    return {"status": "running", "message": "TrackMySpend API is up."}


@app.get("/health")
def health():
    return {"status": "ok"}
