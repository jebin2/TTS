from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.db.database import init_db
from custom_logger import logger_config as logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("="*60)
    logger.info("TTS Runner API Server Starting Up")
    logger.info("="*60)
    logger.info("Worker will start automatically on first request")
    logger.info("Audio files will be retained for 10 days")
    logger.info("="*60)
    
    await init_db()
    yield
    logger.info("TTS Runner API Server Shutting Down")

app = FastAPI(title="TTS Runner API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
