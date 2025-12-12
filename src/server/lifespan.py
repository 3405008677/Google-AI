"""FastAPI lifespan hook，统一处理启动与关闭时的记录。"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .logging_setup import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context that logs startup/shutdown.
    
    优雅处理关闭过程中的异常，避免在正常关闭时显示不必要的错误消息。
    当应用程序收到中断信号（如 Ctrl+C）时，关闭过程中的 CancelledError 是正常行为。
    """
    logger.info("应用正在启动...")
    
    try:
        yield
    except asyncio.CancelledError:
        # 当应用程序被中断时，这是正常行为
        # 在关闭阶段可能会遇到 CancelledError，这是预期的
        logger.debug("应用程序收到取消信号")
        raise
    finally:
        # 关闭阶段的处理
        try:
            logger.info("应用正在关闭...")
        except asyncio.CancelledError:
            # 在关闭过程中，异步任务可能会被取消，这是正常行为
            # 不需要记录为错误，直接重新抛出以便 Starlette 正确处理
            raise
        except Exception as e:
            # 记录其他意外错误，但不影响关闭过程
            logger.warning(f"关闭过程中发生异常（可忽略）: {e}", exc_info=False)
