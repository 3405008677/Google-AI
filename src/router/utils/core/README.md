# src/router/utils/core 目录

> 路由层核心基础：异常定义与统一错误处理。

---

## 文件结构

```
core/
├── __init__.py       # 导出异常类与注册函数
└── exceptions.py     # 异常定义与处理器
```

---

## 异常体系

### 基类

```python
class RouterError(Exception):
    """路由层基础异常"""
    
    def __init__(
        self,
        message: str,
        code: str = "ROUTER_ERROR",
        status_code: int = 400,
        details: dict = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
```

### 内置异常

| 异常类 | 状态码 | 错误码 | 使用场景 |
|:---|:---|:---|:---|
| `RouterError` | 400 | ROUTER_ERROR | 通用路由错误 |
| `AuthenticationError` | 401 | AUTHENTICATION_ERROR | Token 无效/过期 |
| `AuthorizationError` | 403 | AUTHORIZATION_ERROR | 权限不足 |
| `NotFoundError` | 404 | NOT_FOUND | 资源不存在 |
| `ValidationError` | 422 | VALIDATION_ERROR | 参数校验失败 |
| `RateLimitError` | 429 | RATE_LIMIT_EXCEEDED | 请求过于频繁 |
| `InternalError` | 500 | INTERNAL_ERROR | 服务内部错误 |

---

## 统一错误响应

### 响应格式

```json
{
  "error": {
    "code": "AUTHENTICATION_ERROR",
    "message": "Token 已过期",
    "details": {
      "expired_at": "2024-01-15T10:00:00Z"
    },
    "trace_id": "abc123-def456"
  }
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|:---|:---|:---|
| `code` | string | 错误码（机器可读） |
| `message` | string | 错误信息（人类可读） |
| `details` | object | 详细信息（可选） |
| `trace_id` | string | 追踪 ID（便于排查） |

---

## 使用示例

### 抛出异常

```python
from src.router.utils.core import (
    AuthenticationError,
    NotFoundError,
    ValidationError,
)

# 认证失败
raise AuthenticationError("Token 已过期")

# 资源不存在
raise NotFoundError(
    message="用户不存在",
    details={"user_id": 123}
)

# 参数校验失败
raise ValidationError(
    message="参数无效",
    details={"field": "email", "error": "格式不正确"}
)
```

### 注册异常处理器

```python
from src.router.utils.core import register_exception_handlers

# 在应用启动时注册
def create_app():
    app = FastAPI()
    register_exception_handlers(app)
    return app
```

---

## 日志记录

异常处理器会自动记录错误日志：

```python
# 4xx 错误：WARNING 级别
logger.warning(f"[{trace_id}] {error.code}: {error.message}")

# 5xx 错误：ERROR 级别 + 堆栈
logger.error(f"[{trace_id}] {error.code}: {error.message}", exc_info=True)
```
