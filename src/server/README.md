# src/server 目录

> FastAPI 应用组装与服务启动层。

---

## 职责

1. **创建 FastAPI 实例**：注册路由、中间件、异常处理器。
2. **生命周期管理**：处理 startup/shutdown 事件。
3. **日志初始化**：配置控制台与文件日志。
4. **SSL 支持**：可选的 HTTPS 启动。
5. **Uvicorn 封装**：提供统一的启动入口。

---

## 文件结构

```
server/
├── __init__.py        # 导出 create_app, initServer
├── app.py             # 创建 FastAPI 应用
├── server.py          # Uvicorn 启动封装
├── lifespan.py        # 生命周期事件处理
├── logging_setup.py   # 日志器配置
├── exceptions.py      # 全局异常处理器
├── middlewares.py     # 服务级中间件
└── ssl_utils.py       # SSL 参数生成
```

---

## 核心流程

### 应用创建 (app.py)

```python
def create_app() -> FastAPI:
    app = FastAPI(
        title="Google-AI Service",
        lifespan=lifespan,
    )
    
    # 1. 注册异常处理器
    register_exception_handlers(app)
    
    # 2. 添加服务级中间件
    add_middlewares(app)
    
    # 3. 挂载静态目录
    app.mount("/static", StaticFiles(...))
    
    # 4. 初始化路由（可选）
    if settings.ENABLE_ROUTER:
        initRouter(app)
    
    return app
```

### 服务启动 (server.py)

```python
def initServer():
    """统一启动入口，供 main.py 调用"""
    ssl_config = get_ssl_config()
    
    uvicorn.run(
        "src.server:create_app",
        host=settings.HOST,
        port=settings.PORT,
        workers=settings.WORKERS,
        **ssl_config,
    )
```

---

## 日志配置 (logging_setup.py)

### 特性

- **多输出目标**：控制台（彩色）+ 文件（轮转）。
- **结构化日志**：可选 JSON 格式，便于接入 ELK/Loki。
- **级别控制**：通过 `LOG_LEVEL` 环境变量配置。

### 使用

```python
from src.server.logging_setup import logger

logger.info("服务启动")
logger.error("发生错误", exc_info=True)
```

---

## SSL 配置 (ssl_utils.py)

### 环境变量

| 变量 | 说明 |
|:---|:---|
| `SSL_ENABLED` | 是否启用 HTTPS |
| `SERVER_SSL_CERTFILE` | 证书文件路径 |
| `SERVER_SSL_KEYFILE` | 私钥文件路径 |

> **注意**：为避免与系统 SSL 环境变量冲突，项目使用 `SERVER_SSL_*` 前缀。

---

## 生命周期 (lifespan.py)

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("服务启动中...")
    await initialize_resources()
    
    yield
    
    # Shutdown
    logger.info("服务关闭中...")
    await cleanup_resources()
```
