"""封裝 uvicorn 相關啟動流程，讓 main.py 只需呼叫 initServer。"""

import uvicorn

from .app import app, config
from .logging_setup import logger
from .ssl_utils import build_ssl_kwargs


def initServer():
    """Bootstrap FastAPI with uvicorn and print helpful runtime metadata."""
    logger.info("🚀 服务启动中")
    logger.info("📍 地址: %s://%s:%s", "https" if config.ssl_enabled else "http", config.host, config.port)
    logger.info("🔧 调试模式: %s", config.debug)
    logger.info("📁 静态资源: %s", config.static_dir)
    logger.info("📦 上传限制: %s bytes", config.max_upload_size)
    logger.info("=" * 50)

    logger.info('config.host: %s', config.host)
    logger.info('config.port: %s', config.port)

    try:
        uvicorn.run(
            app,
            host='0.0.0.0',  # 临时修改为 '0.0.0.0' 以测试网络访问
            port=config.port,
            log_level="debug" if config.debug else "info",
            access_log=True,
            **build_ssl_kwargs(config),
        )
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在优雅关闭...")
    except Exception:
        logger.exception("服务器启动失败")
        raise
