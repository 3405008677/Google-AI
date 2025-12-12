# Google-AI

> 一个可扩展的 AI Web 服务：支持多模型（Gemini / Qwen / 自定义 OpenAI 兼容接口）、Supervisor/Worker 任务编排（LangGraph）、性能优化层（规则引擎 + 语义缓存）、以及面向生产的路由中间件（追踪/限流/认证）与可观测性（日志/健康检查/指标）。

---

## 1. 项目定位与目标

### 1.1 这个项目解决什么问题？
当你希望把“多个大模型能力 + 工具调用 + 复杂任务拆解 + API 服务化”组合成一个可部署、可扩展、可治理的服务时，常见痛点包括：

- **多模型接入碎片化**：不同供应商 SDK、鉴权方式、接口形态各异。
- **复杂任务需要编排**：一次请求往往不是一句 prompt 就能解决，需要拆解、规划、调用工具、聚合结果。
- **成本与延迟不可控**：重复问题重复调用昂贵的 LLM，导致费用和延迟暴涨。
- **缺少治理能力**：缺少认证、限流、追踪、健康检查，难以进入生产环境。

本项目的目标是提供一个“工程化”的骨架：
- **对外**是稳定的 HTTP API（FastAPI），可观测、可控。
- **对内**是可插拔的模型路由、Agent/Supervisor 编排、工具体系与性能层。

### 1.2 适用场景
- 将 LLM 能力封装成内部服务（聊天、问答、任务型助手）。
- 多步骤任务（检索 + 分析 + 报告）需要可视化进度（SSE 流式）。
- 需要在调用 LLM 前做“便宜的判断”（规则命中、缓存命中）。
- 需要 JWT 登录、限流、防刷、链路追踪等基础治理。

---

## 2. 技术栈一览（框架与选型）

### 2.1 Web 框架：FastAPI + Starlette
- **选型原因**
  - **异步优先**：天然适合高并发 I/O 场景（调用外部模型 API、搜索 API 等）。
  - **类型标注友好**：配合 Pydantic，可快速获得可靠的请求/响应校验与 OpenAPI 文档。
  - **依赖注入机制（Depends）**：使服务具备更好的可测试性与模块解耦。
- **核心优势**
  - 性能优秀（基于 Starlette/ASGI）。
  - 自动生成交互式 API 文档（可在 debug 模式开启）。

### 2.2 ASGI Server：Uvicorn
- **选型原因**：成熟、轻量、社区使用广，启动配置简单。
- **优势**：与 FastAPI/Starlette 生态契合；支持 HTTP/1.1、Websocket（本项目也引入 `websockets` 依赖）。

### 2.3 数据与校验：Pydantic v2
- **选型原因**：FastAPI 默认生态；用于 API 的请求/响应模型。
- **优势**：更严格的数据校验与更好的类型表达能力；提升接口契约稳定性。

### 2.4 配置管理：python-dotenv + dataclass 配置
- **选型原因**：
  - `.env` 是本地开发最通用的方式。
  - dataclass 配置可读性强、类型更明确，利于校验与提示。
- **优势**：
  - 清晰的“环境变量 -> 配置对象”映射。
  - 可在启动时做校验并输出友好警告。

> 注意：项目里存在两套配置入口：`src/config.py` 与 `src/core/settings.py`，分别面向“应用启动”和“统一配置中心”。它们可以并存，也可后续统一到单一入口。

### 2.5 Agent 编排：LangChain + LangGraph
- **选型原因**
  - **LangChain** 负责消息结构、工具协议等生态对接。
  - **LangGraph** 适合把复杂任务拆成一个可执行的图（Graph），天然支持多节点/多步骤流程。
- **优势**
  - 编排逻辑更工程化：从“脚本式 if/else”升级为“可维护的状态机/工作流”。
  - 更容易扩展 Worker、插入检查点、加入新的节点能力。

### 2.6 性能层：Redis + sentence-transformers + 规则引擎
- **语义缓存（Semantic Cache）**
  - **选型原因**：Redis 部署简单、可扩展；sentence-transformers 提供文本向量化能力。
  - **优势**：
    - 对重复/相似问题做到“0 次 LLM 调用”，显著降低成本与延迟。
    - 可通过阈值（`SEMANTIC_CACHE_THRESHOLD`）控制命中率与准确性。
- **规则引擎（Rule Engine）**
  - **选型原因**：对“问候/帮助/清理历史”等非推理类指令，不必调用 LLM。
  - **优势**：更快、更便宜、更可控；减少幻觉与不确定输出。

### 2.7 搜索能力：Tavily（可选）
- **选型原因**：提供一套简单的 Web 搜索 API 接入。
- **优势**：为需要联网检索的 Worker 提供工具能力。

### 2.8 安全：JWT（PyJWT）+ bcrypt
- **选型原因**
  - JWT 易于在前后端间传递与扩展 claims。
  - bcrypt 用于更可靠的密码哈希（本项目授权模块包含示例实现与安全提示）。
- **优势**
  - 可无状态扩展（多实例部署时仍需考虑 Token 黑名单的持久化方案）。

---

## 3. 总体架构（从请求到响应）

### 3.1 模块分层（高层视图）

```
Client
  |
  v
FastAPI App (src/server)
  |
  +--> Router System (src/router)
  |      +--> Tracing / Auth / RateLimit Middlewares (src/router/utils)
  |      +--> Health & Metrics (src/router/health.py)
  |      +--> Authorization(JWT) (src/router/services/authorization)
  |      +--> Agents API (src/router/agents/api.py)
  |
  +--> Agents Layer (src/router/agents)
         +--> Performance Layer (rule engine + semantic cache)
         +--> Supervisor (LangGraph workflow)
         +--> Workers / Tools
                 +--> Tools Registry (src/common/function_calls)
                 +--> Prompt Manager (src/common/prompts)
```

### 3.2 一次典型请求的处理流程
1. **Uvicorn 接收请求**（`src/server/server.py`）。
2. **FastAPI app 组装**（`src/server/app.py`）：注册中间件、异常处理器、静态目录、（可选）加载路由。
3. **路由层中间件链**（`src/router/index.py`）：
   - 追踪（生成/透传 `X-Trace-ID`，记录耗时）
   - 认证（检查 Authorization，写入 `request.state.auth_token`）
   - 限流（滑动窗口，超限直接 429）
4. **进入业务路由**：
   - 健康检查/指标：`/health`、`/ready`、`/status`、`/metrics`
   - 授权：`/auth/login`、`/auth/refresh`、`/auth/validate`、`/auth/logout`、`/auth/me`
   - Agent：`/agents/chat`（非流式）或 `/agents/chat/stream`（SSE 流式）
5. **（可选）性能层速通**：规则命中或语义缓存命中则直接返回。
6. **进入 Supervisor 工作流**：将任务拆解为步骤并调度 Worker。
7. **（流式模式）通过 SSE 实时推送事件**：开始/进度/答案/完成。

---

## 4. 目录结构（根目录导览）

- `src/`：核心源码目录（内部还有更细的 README）。
- `static/`：静态资源目录（默认挂载到 `/static`）。
- `env.example`：环境变量示例（建议复制为 `.env`）。
- `requirements.txt`：Python 依赖锁定。

---

## 5. 关键特性详解

### 5.1 路由治理：追踪、认证、限流
- **追踪（Tracing）**
  - 自动生成/透传 TraceID（`X-Trace-ID` / `X-Request-ID`）。
  - 响应会回传 `X-Trace-ID` 与 `X-Router-Process-Time`。
- **认证（Auth）**
  - 目前路由中间件提供“可扩展的 token 校验钩子”。
  - JWT 授权能力位于 `src/router/services/authorization`（登录/刷新/验证/登出）。
- **限流（Rate Limit）**
  - 采用滑动窗口，基于 IP 统计，超限直接返回 429。
  - 支持跳过路径（健康检查、静态资源等）。

### 5.2 Agent/Supervisor：复杂任务编排
- **为什么需要 Supervisor/Worker？**
  - 复杂问题往往需要“分解步骤 + 逐步执行 + 汇总结果”。
  - 将能力分成 Worker（可复用、可测试），由 Supervisor 调度。
- **为什么用 LangGraph？**
  - 把流程显式建模成图/状态机，利于扩展、观测和维护。

### 5.3 性能层：规则引擎 + 语义缓存
- **规则引擎**
  - 对高频固定意图（问候/帮助/清理等）直接命中。
- **语义缓存**
  - 使用句向量相似度（阈值默认 0.95）命中“相似问题”。
  - Redis 与向量模型不可用时自动降级为禁用。

### 5.4 工具体系：function calling Registry
- 工具定义可由 YAML 配置加载，统一输出 OpenAI function calling 结构。
- 支持为不同 Worker 指定可用工具集合。

### 5.5 可观测性：日志 + 健康检查 + 指标
- **日志**：支持控制台彩色输出与文件轮转；可切换结构化 JSON 日志，便于接入 ELK/Loki。
- **健康检查**：
  - `/health`：存活探针
  - `/ready`：就绪探针（Worker/依赖检查）
  - `/status`：详细状态
  - `/metrics`：指标

### 5.6 SSL/HTTPS（可选）
- 通过 `SSL_ENABLED`、`SERVER_SSL_CERTFILE`、`SERVER_SSL_KEYFILE` 控制。
- 为避免与系统库冲突，项目刻意**不用** `SSL_CERT_FILE` / `SSL_KEY_FILE`。

---

## 6. 快速开始（开发运行）

### 6.1 环境要求
- Python **>= 3.9**（建议 3.10+）
- Windows / Linux / macOS 均可

### 6.2 安装依赖

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 6.3 配置环境变量
1. 复制配置示例：

```bash
copy env.example .env
```

2. 至少配置一个模型（示例：Gemini）：
- `GEMINI_API_KEY=...`

可选：Redis（用于语义缓存）、Tavily（用于搜索工具）。

### 6.4 启动服务

```bash
python -m src.main
```

启动后默认访问：
- 本地：`http://127.0.0.1:8080`
- 文档：debug 模式下可用 `/docs`、`/redoc`

> `src/main.py` 对 Windows 控制台编码做了兼容处理，减少中文输出乱码问题。

---

## 7. 配置说明（env.example 对照）

### 7.1 服务器
- `HOST` / `PORT` / `WORKERS` / `DEBUG` / `LOG_LEVEL`
- `ENABLE_ROUTER`：是否加载路由（可用于“只启动骨架”加速启动）
- `MAX_UPLOAD_SIZE` / `STATIC_DIR`

### 7.2 模型
- Gemini：`GEMINI_API_KEY` / `GEMINI_MODEL` / `GEMINI_TIMEOUT` / `GEMINI_MAX_RETRIES`
- Qwen：`QWEN_API_KEY` / `QWEN_MODEL` / `QWEN_BASE_URL` / `QWEN_TIMEOUT` / `QWEN_MAX_RETRIES`
- 自定义模型：`SELF_MODEL_BASE_URL` / `SELF_MODEL_NAME` / `SELF_MODEL_API_KEY`

### 7.3 认证
- `JWT_SECRET_KEY`（生产环境务必设置强随机值）
- `AUTH_ADMIN_USERNAME` / `AUTH_ADMIN_PASSWORD`

### 7.4 性能层（可选）
- Redis：`REDIS_HOST` / `REDIS_PORT` / `REDIS_DB` / `REDIS_PASSWORD`
- `ENABLE_SEMANTIC_CACHE` / `ENABLE_RULE_ENGINE` / `SEMANTIC_CACHE_THRESHOLD`

---

## 8. API 速览

### 8.1 健康检查
- `GET /health`
- `GET /ready`
- `GET /status`
- `GET /metrics`

### 8.2 授权（JWT）
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/validate`
- `POST /auth/logout`
- `GET /auth/me`

### 8.3 Agents（Supervisor/Worker）
- `POST /agents/chat`：非流式
- `POST /agents/chat/stream`：SSE 流式
- `GET /agents/chat/history/{thread_id}`：会话历史
- `GET /agents/workers`：列出 Worker
- `POST /agents/workers/reset`：重置 Worker/服务

---

## 9. 生产化建议（实践经验）

### 9.1 安全
- **务必设置** `JWT_SECRET_KEY`，并使用强随机值。
- 生产环境建议将 Token 黑名单从内存迁移到 Redis（避免多实例不一致）。
- 在反向代理后部署时，建议正确配置/信任 `X-Forwarded-For`，并限制来源。

### 9.2 稳定性与成本
- 优先启用规则引擎与语义缓存，降低重复调用成本。
- 对外部模型 API 调用设置超时与重试（项目中已为模型配置提供相关字段）。

### 9.3 可观测性
- 建议开启结构化日志（JSON）接入日志平台。
- 保留 TraceID，便于排查某一次请求的端到端链路。

---

## 10. 选型总结（为什么这样组合）

- **FastAPI + Uvicorn**：兼顾性能、工程化与开发效率，是 Python 服务化 LLM 能力的“最短路径”。
- **LangGraph**：把复杂任务显式化为可维护的工作流图，天然适合多 Worker 调度。
- **Redis + sentence-transformers**：用简单可部署的组件实现“相似问题直接返回”，立竿见影降低成本。
- **JWT + 中间件治理**：让服务具备生产必需的认证、限流、防刷与追踪能力。

---

## 11. 进一步阅读
- `src/README.md`：源码总览
- `src/router/README.md`：路由体系
- `src/router/agents/README.md`：Agent/Supervisor 架构
- `src/router/agents/performance_layer/README.md`：性能层
- `src/common/function_calls/README.md`：工具注册与调用
