"""FastAPI lifespan hook，統一處理啟動與關閉時的側錄。"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .logging_setup import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context that logs startup/shutdown."""
    logger.info("应用正在启动...")
    yield
    logger.info("应用正在关闭...")
