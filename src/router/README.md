# src/router 目录

> API 路由系统：中间件链、健康检查、Agent API、授权服务。

---

## 架构概览

```
                              ┌─────────────────────────────────────┐
                              │           FastAPI App               │
                              └─────────────────────────────────────┘
                                              │
                              ┌───────────────▼───────────────┐
                              │        router/index.py         │
                              │       (initRouter 入口)        │
                              └───────────────┬───────────────┘
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    │                         │                         │
           ┌────────▼────────┐       ┌────────▼────────┐       ┌────────▼────────┐
           │   Middlewares   │       │  Health Check   │       │   Agent API     │
           │  (utils/中间件)  │       │   (health.py)   │       │  (agents/api)   │
           └─────────────────┘       └─────────────────┘       └─────────────────┘
                    │
    ┌───────────────┼───────────────┐
    │               │               │
┌───▼───┐      ┌────▼────┐    ┌─────▼─────┐
│Tracing│      │  Auth   │    │Rate Limit │
└───────┘      └─────────┘    └───────────┘
```

---

## 目录结构

```
router/
├── __init__.py          # 导出 initRouter
├── index.py             # 路由初始化入口
├── health.py            # 健康检查端点
│
├── agents/              # Agent/Supervisor 架构
│   ├── api.py           # Agent API 端点
│   ├── supervisor/      # Supervisor 核心实现
│   ├── performance_layer/ # 性能优化层
│   └── AI/              # 模型适配层
│
├── services/            # 业务服务
│   └── authorization/   # JWT 授权服务
│
└── utils/               # 路由工具
    ├── core/            # 异常定义
    └── middlewares/     # 中间件实现
```

---

## 初始化流程 (index.py)

```python
def initRouter(app: FastAPI):
    """路由系统初始化入口"""
    
    # 1. 注册中间件（顺序重要：后注册先执行）
    register_rate_limit_middleware(app)  # 限流
    register_auth_middleware(app)        # 认证
    register_tracing_middleware(app)     # 追踪（最先执行）
    
    # 2. 注册健康检查端点
    register_health_routes(app)
    
    # 3. 注册授权服务
    register_auth_routes(app, prefix="/auth")
    
    # 4. 注册 Agent API
    register_agent_routes(app, prefix="/agents")
```

---

## 端点一览

### 健康检查

| 端点 | 方法 | 说明 |
|:---|:---|:---|
| `/health` | GET | 存活探针（Liveness） |
| `/ready` | GET | 就绪探针（Readiness） |
| `/status` | GET | 详细状态信息 |
| `/metrics` | GET | Prometheus 指标 |

### 授权服务

| 端点 | 方法 | 说明 |
|:---|:---|:---|
| `/auth/login` | POST | 登录获取 Token |
| `/auth/refresh` | POST | 刷新 Access Token |
| `/auth/validate` | POST | 验证 Token |
| `/auth/logout` | POST | 登出（Token 拉黑） |
| `/auth/me` | GET | 获取当前用户信息 |

### Agent API

| 端点 | 方法 | 说明 |
|:---|:---|:---|
| `/agents/chat` | POST | 非流式对话 |
| `/agents/chat/stream` | POST | SSE 流式对话 |
| `/agents/chat/history/{thread_id}` | GET | 获取会话历史 |
| `/agents/workers` | GET | 列出可用 Worker |
| `/agents/workers/reset` | POST | 重置 Worker 状态 |

---

## 中间件执行顺序

FastAPI 中间件执行顺序为"后注册先执行"：

```
请求 → Tracing → Auth → RateLimit → 路由处理 → RateLimit → Auth → Tracing → 响应
```

1. **Tracing**：生成/透传 TraceID，记录请求耗时。
2. **Auth**：校验 Authorization 头，写入 `request.state.auth_token`。
3. **RateLimit**：基于 IP 的滑动窗口限流，超限返回 429。

---

## 子目录文档

| 目录 | 说明 | 详细文档 |
|:---|:---|:---|
| `agents/` | Agent/Supervisor 架构 | [README](agents/README.md) |
| `services/` | 业务服务（授权） | [README](services/README.md) |
| `utils/` | 中间件与异常 | [README](utils/README.md) |
