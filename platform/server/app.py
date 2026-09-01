import os
import logging
from contextlib import asynccontextmanager
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from server.services.db import init_db
from server.routers import auth, github_setup, registrations

logger = logging.getLogger('safelane.platform')
logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database...")
    await init_db()
    yield
    logger.info("Shutting down...")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(github_setup.router, prefix="/api/github", tags=["github"])
app.include_router(registrations.router, prefix="/api/registrations", tags=["registrations"])

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Mount frontend
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
frontend_dir = os.path.join(BASE_DIR, "frontend")
if not os.path.exists(frontend_dir):
    frontend_dir = os.path.abspath("platform/frontend") if os.path.exists("platform/frontend") else os.path.abspath("frontend")

app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
