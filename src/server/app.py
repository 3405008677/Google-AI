"""负责组装 FastAPI 应用：路由、中间件、异常处理器等。"""

import mimetypes
from typing import Optional

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from loguru import logger  # 推荐使用 loguru 替代标准 logging

from src.config import get_config
from src.router.index import initRouter

from .exceptions import register_exception_handlers
from .lifespan import lifespan
from .middlewares import LoggingMiddleware

# 确保在提供静态文件服务前注册自定义MIME类型
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")

# 全局配置实例
config = get_config()


def create_app(config_overrides: Optional[dict] = None) -> FastAPI:
    """
    创建并配置一个包含所有服务组件的FastAPI实例

    Args:
        config_overrides: 配置覆盖参数，用于测试场景

    Returns:
        配置完成的FastAPI应用实例
    """
    from dataclasses import asdict
    
    # 将dataclass转换为字典并合并配置（优先使用覆盖配置）
    config_dict = asdict(config)
    app_config = {**config_dict, **(config_overrides or {})}

    # 创建FastAPI应用实例
    app = FastAPI(
        title="Python Web Server",
        version="1.0.0",
        debug=app_config.get("debug", config.debug),
        lifespan=lifespan,
        docs_url="/docs" if app_config.get("debug") else None,
        redoc_url="/redoc" if app_config.get("debug") else None,
    )

    # 注册中间件
    app.add_middleware(LoggingMiddleware)

    # 注册异常处理器
    register_exception_handlers(app, config)

    # 确保静态目录存在后再挂载，避免应用启动时抛出异常
    static_dir = app_config.get("static_dir", config.static_dir)
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=static_dir, check_dir=False), name="static")

    # 初始化路由
    initRouter(app)

    logger.info("FastAPI应用初始化完成")
    return app


# 创建应用实例
app = create_app()
