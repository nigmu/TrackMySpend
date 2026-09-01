import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import FRONTEND_ORIGIN
from .core.logging import configure_logging, get_logger

os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
configure_logging()
logger = get_logger(__name__)

from .accounts.routes import router as accounts_router
from .filters.routes import router as filters_router
from .ingestion.routes import router as ingestion_router
from .parsing.routes import router as parsing_router
from .scheduler import poller_loop


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("SERVER_STARTUP")
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        FRONTEND_ORIGIN,
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(accounts_router)
app.include_router(filters_router)
app.include_router(ingestion_router)
app.include_router(parsing_router)


@app.get("/")
def root():
    return {"status": "running", "message": "TrackMySpend API is up."}
