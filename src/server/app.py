"""负责组装 FastAPI 应用：路由、中间件、异常处理器等。"""

import mimetypes
from typing import Optional

from dataclasses import asdict, replace
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.config import AppConfig, get_config

from .exceptions import register_exception_handlers
from .lifespan import lifespan
from .logging_setup import logger
from .middlewares import LoggingMiddleware

# 确保在提供静态文件服务前注册自定义MIME类型
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")

# 全局配置实例（原始配置，保持与 uvicorn 启动参数一致）
config = get_config()


def _merge_config(overrides: Optional[dict]) -> AppConfig:
    """
    合并配置覆盖项，返回新的 AppConfig 实例。
    未知字段会被忽略，避免在 tests 中传入无效键导致报错。
    """
    if not overrides:
        return config

    # 仅保留 AppConfig 中存在的字段
    valid_overrides = {k: v for k, v in overrides.items() if hasattr(config, k)}
    return replace(config, **valid_overrides)


def create_app(config_overrides: Optional[dict] = None) -> FastAPI:
    """
    创建并配置一个包含所有服务组件的FastAPI实例

    Args:
        config_overrides: 配置覆盖参数，用于测试场景

    Returns:
        配置完成的FastAPI应用实例
    """
    effective_config = _merge_config(config_overrides)
    config_dict = asdict(effective_config)

    # 创建FastAPI应用实例
    app = FastAPI(
        title="Python Web Server",
        version="1.0.0",
        debug=config_dict.get("debug", config.debug),
        lifespan=lifespan,
        docs_url="/docs" if config_dict.get("debug") else None,
        redoc_url="/redoc" if config_dict.get("debug") else None,
    )

    # 将最终配置挂到 app.state，便于后续访问
    app.state.config = effective_config

    # 注册中间件
    app.add_middleware(LoggingMiddleware)

    # 注册异常处理器
    register_exception_handlers(app, effective_config)

    # 确保静态目录存在后再挂载，避免应用启动时抛出异常
    static_dir = config_dict.get("static_dir", config.static_dir)
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=static_dir, check_dir=False), name="static")

    # 初始化路由（默认关闭以加快启动，可通过 ENABLE_ROUTER 控制）
    if config_dict.get("enable_router", False):
        from src.router.index import initRouter  # 延迟导入，避免不必要的依赖
        initRouter(app)
    else:
        logger.info("路由未加载（ENABLE_ROUTER=false），启动更快")

    logger.info("FastAPI应用初始化完成")
    return app


# 创建应用实例
app = create_app()
