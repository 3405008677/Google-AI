# src/router/utils/middlewares 目录

> 路由层中间件实现：追踪、认证、限流。

---

## 中间件列表

| 文件 | 中间件 | 职责 |
|:---|:---|:---|
| `tracing.py` | TracingMiddleware | 链路追踪 |
| `auth.py` | AuthMiddleware | 认证校验 |
| `rate_limit.py` | RateLimitMiddleware | 请求限流 |

---

## 执行顺序

FastAPI 中间件遵循"洋葱模型"，后注册的先执行：

```
┌──────────────────────────────────────────────────────────┐
│                    TracingMiddleware                     │
│  ┌────────────────────────────────────────────────────┐  │
│  │                   AuthMiddleware                   │  │
│  │  ┌──────────────────────────────────────────────┐  │  │
│  │  │              RateLimitMiddleware             │  │  │
│  │  │  ┌────────────────────────────────────────┐  │  │  │
│  │  │  │           Route Handler               │  │  │  │
│  │  │  └────────────────────────────────────────┘  │  │  │
│  │  └──────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

注册顺序（`router/index.py`）：

```python
register_rate_limit_middleware(app)  # 最后执行
register_auth_middleware(app)        # 中间执行
register_tracing_middleware(app)     # 最先执行
```

---

## tracing.py（链路追踪）

### 功能

- 从请求头读取或自动生成 `X-Trace-ID`。
- 将 TraceID 注入日志上下文。
- 响应头返回 `X-Trace-ID` 和 `X-Router-Process-Time`。

### 请求头

| Header | 说明 |
|:---|:---|
| `X-Trace-ID` | 链路追踪 ID（优先读取） |
| `X-Request-ID` | 请求 ID（备选） |

### 响应头

| Header | 说明 |
|:---|:---|
| `X-Trace-ID` | 本次请求的追踪 ID |
| `X-Router-Process-Time` | 请求处理耗时（毫秒） |

---

## auth.py（认证）

### 功能

- 检查 `Authorization: Bearer <token>` 头。
- 解析 Token 并写入 `request.state.auth_token`。
- 支持配置跳过路径。

### 跳过路径（默认）

```python
SKIP_PATHS = [
    "/health",
    "/ready",
    "/status",
    "/metrics",
    "/auth/login",
    "/docs",
    "/redoc",
    "/openapi.json",
]
```

### 使用

```python
# 在路由中获取认证信息
@router.get("/protected")
async def protected(request: Request):
    token = request.state.auth_token
    user_id = token.get("sub")
    ...
```

---

## rate_limit.py（限流）

### 功能

- 滑动窗口算法，基于客户端 IP。
- 默认限制：100 请求/分钟。
- 超限返回 `429 Too Many Requests`。

### 配置

| 环境变量 | 说明 | 默认值 |
|:---|:---|:---|
| `RATE_LIMIT_REQUESTS` | 窗口内最大请求数 | 100 |
| `RATE_LIMIT_WINDOW` | 窗口大小（秒） | 60 |

### 响应头

| Header | 说明 |
|:---|:---|
| `X-RateLimit-Limit` | 窗口内最大请求数 |
| `X-RateLimit-Remaining` | 剩余请求数 |
| `X-RateLimit-Reset` | 窗口重置时间（Unix 时间戳） |

### 跳过路径

```python
SKIP_PATHS = [
    "/health",
    "/ready",
    "/static",
]
```

---

## 添加自定义中间件

```python
# src/router/utils/middlewares/my_middleware.py

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class MyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 前置处理
        ...
        
        response = await call_next(request)
        
        # 后置处理
        ...
        
        return response

def register_my_middleware(app):
    app.add_middleware(MyMiddleware)
```
