from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .core.config import CORS_ORIGINS, SMS_INGEST_TOKEN
from .core.logging import RequestLogMiddleware, configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

from .companion.routes import RELEASES_DIR
from .companion.routes import router as companion_router
from .logs.routes import router as logs_router
from .sms.routes import router as sms_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("SERVER_STARTUP")
    if not SMS_INGEST_TOKEN:
        logger.warning("sms ingest auth disabled")
    RELEASES_DIR.mkdir(parents=True, exist_ok=True)
    yield
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
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SMS pipeline (src/sms): TMS Companion -> POST /sms/ingest_and_parse stores the
# raw row and classifies it before commit.
# logs (app_event_logs) and companion (TMS Companion OTA) sit beside it.
app.include_router(sms_router)
app.include_router(logs_router)
app.include_router(companion_router)

RELEASES_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/releases", StaticFiles(directory=RELEASES_DIR), name="releases")


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    if request.url.path == "/sms/ingest_and_parse":
        logger.warning("sms ingest validation failed errors=%s", exc.errors())
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.get("/")
def root():
    return {"status": "running", "message": "TrackMySpend API is up."}


@app.get("/health")
def health():
    return {"status": "ok"}
