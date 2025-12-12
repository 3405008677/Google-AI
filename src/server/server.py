"""封装 uvicorn 相关启动流程，让 main.py 只需调用 initServer。"""

import socket
import sys
import uvicorn

from .app import app, config
from .logging_setup import logger
from .ssl_utils import build_ssl_kwargs


def _is_port_in_use(host: str, port: int) -> bool:
    """检查端口是否已被占用"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


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

    # 检查端口是否已被占用
    if _is_port_in_use(config.host, config.port):
        error_msg = (
            f"\n❌ 错误：端口 {config.port} 已被占用！\n"
            f"   请执行以下命令检查并终止占用该端口的进程：\n"
            f"   Windows: netstat -ano | findstr :{config.port}\n"
            f"   然后使用: Stop-Process -Id <PID> -Force\n"
            f"   或者修改环境变量 PORT 使用其他端口\n"
        )
        logger.error(error_msg)
        print(error_msg, file=sys.stderr)
        sys.exit(1)

    try:
        uvicorn.run(
            app,
            host=config.host,
            port=config.port,
            log_level="debug" if config.debug else "info",
            access_log=True,
            **build_ssl_kwargs(config),
        )
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在优雅关闭...")
    except OSError as e:
        if "10048" in str(e) or "address already in use" in str(e).lower():
            error_msg = (
                f"\n❌ 错误：端口 {config.port} 已被占用！\n"
                f"   请执行以下命令检查并终止占用该端口的进程：\n"
                f"   Windows: netstat -ano | findstr :{config.port}\n"
                f"   然后使用: Stop-Process -Id <PID> -Force\n"
                f"   或者修改环境变量 PORT 使用其他端口\n"
            )
            logger.error(error_msg)
            print(error_msg, file=sys.stderr)
        else:
            logger.exception("服务器启动失败")
        raise
    except Exception:
        logger.exception("服务器启动失败")
        raise
