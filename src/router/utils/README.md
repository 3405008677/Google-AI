# src/router/utils 目录

> 路由层通用工具：异常处理与中间件。

---

## 目录结构

```
utils/
├── __init__.py          # 统一导出
├── core/                # 路由核心
│   └── exceptions.py    # 异常定义与处理器
└── middlewares/         # 中间件集合
    ├── tracing.py       # 链路追踪
    ├── auth.py          # 认证校验
    └── rate_limit.py    # 请求限流
```

---

## 异常处理 (core/)

### 统一错误响应格式

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "请求参数无效",
    "details": {...},
    "trace_id": "abc123"
  }
}
```

### 内置异常类型

| 异常 | HTTP 状态码 | 说明 |
|:---|:---|:---|
| `RouterError` | 400 | 通用路由错误 |
| `AuthenticationError` | 401 | 认证失败 |
| `AuthorizationError` | 403 | 权限不足 |
| `NotFoundError` | 404 | 资源不存在 |
| `RateLimitError` | 429 | 请求过于频繁 |

---

## 中间件 (middlewares/)

### Tracing（链路追踪）

- 自动生成或透传 `X-Trace-ID` / `X-Request-ID`。
- 响应头返回 `X-Trace-ID` 与 `X-Router-Process-Time`。
- 日志自动关联 TraceID，便于问题排查。

### Auth（认证）

- 检查 `Authorization: Bearer <token>` 头。
- Token 信息写入 `request.state.auth_token`。
- 可配置跳过路径（如健康检查）。

### Rate Limit（限流）

- 滑动窗口算法，基于客户端 IP。
- 默认：100 请求/分钟（可配置）。
- 超限返回 `429 Too Many Requests`。
- 可配置跳过路径（如 `/health`、`/metrics`）。

---

## 子目录文档

- [core/README.md](core/README.md) - 异常处理详解
- [middlewares/README.md](middlewares/README.md) - 中间件详解
