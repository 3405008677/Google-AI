"""封裝 SSL 相關檢查，維持啟動程式邏輯簡潔。"""

from typing import Dict

from .logging_setup import logger


def build_ssl_kwargs(config) -> Dict[str, str]:
    """Decide whether SSL parameters should be passed to uvicorn."""
    if not config.ssl_enabled:
        return {}

    certfile = config.ssl_certfile
    keyfile = config.ssl_keyfile

    if not (certfile and keyfile):
        logger.warning("已启用 SSL，但缺少证书路径设定，将以 HTTP 启动。")
        return {}

    if not (certfile.exists() and keyfile.exists()):
        logger.warning("SSL 证书文件不存在，将以 HTTP 启动。")
        return {}

    return {"ssl_certfile": str(certfile), "ssl_keyfile": str(keyfile)}

