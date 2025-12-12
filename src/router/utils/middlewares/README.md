## src/router/utils/middlewares 目录说明

## 概述
路由层中间件集合，按职责划分：
- 认证（Auth）：校验请求是否携带有效凭证
- 限流（Rate Limit）：限制单位时间请求次数
- 追踪（Tracing）：注入 trace_id 并记录请求链路

## 关键文件
- `auth.py`：认证中间件注册与实现。
- `rate_limit.py`：限流中间件注册与实现。
- `tracing.py`：追踪中间件注册与实现。

## 备注
FastAPI 中间件执行顺序为“后注册先执行”，`router/index.py` 中的注册顺序具有明确含义。
