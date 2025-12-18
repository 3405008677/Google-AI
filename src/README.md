# src 目录

> 项目核心源码区，包含服务启动、FastAPI 应用、路由系统、Agent 架构、工具与配置。

---

## 目录结构

```
src/
├── main.py              # 项目启动入口
├── config.py            # 应用配置（模型连接、启动参数）
│
├── server/              # FastAPI 应用组装与启动
│   ├── app.py           # 创建 FastAPI 实例
│   ├── server.py        # Uvicorn 启动封装
│   ├── lifespan.py      # 生命周期管理
│   ├── logging_setup.py # 日志配置
│   └── ...
│
├── router/              # API 路由系统
│   ├── index.py         # 路由初始化入口
│   ├── health.py        # 健康检查端点
│   ├── agents/          # Agent/Supervisor 核心
│   ├── services/        # 业务服务（如授权）
│   └── utils/           # 中间件（认证/限流/追踪）
│
├── core/                # 核心基础设施
│   ├── settings.py      # 统一配置中心
│   ├── dependencies.py  # FastAPI 依赖注入
│   └── metrics.py       # 指标采集
│
├── common/              # 通用能力
│   ├── prompts/         # 提示词管理
│   └── function_calls/  # 工具注册与调用
│
├── tools/               # 工具实现（时间、搜索等）
│
└── prompts/             # 提示词资源（扩展用）
```

---

## 启动流程

```
main.py
   │
   ├─→ 读取 .env 配置
   │
   ├─→ 初始化日志 (logging_setup.py)
   │
   ├─→ 创建 FastAPI App (server/app.py)
   │     ├─→ 注册异常处理器
   │     ├─→ 挂载静态目录
   │     └─→ 初始化路由 (router/index.py)
   │           ├─→ 注册中间件链
   │           ├─→ 注册健康检查端点
   │           └─→ 注册 Agent API
   │
   └─→ 启动 Uvicorn (server/server.py)
```

---

## 配置体系

项目存在两套配置入口，可并存或按需统一：

| 文件 | 职责 | 使用场景 |
|:---|:---|:---|
| `src/config.py` | 应用启动与模型连接配置 | `AppConfig` 类，面向具体业务模块 |
| `src/core/settings.py` | 统一配置中心 | `settings` 单例，全量配置聚合 |

配置通过 `.env` 或环境变量注入，常用变量：

```ini
# 服务器
HOST=0.0.0.0
PORT=8080
DEBUG=false

# 模型
GEMINI_API_KEY=xxx
QWEN_API_KEY=xxx

# 安全
JWT_SECRET_KEY=your_secure_key
```

---

## 快速导航

| 目录 | 说明 | 详细文档 |
|:---|:---|:---|
| `server/` | FastAPI 应用组装、生命周期、日志 | [README](server/README.md) |
| `router/` | 路由、中间件、Agent API | [README](router/README.md) |
| `core/` | 依赖注入、配置中心、指标 | [README](core/README.md) |
| `common/` | 提示词、工具注册 | [README](common/README.md) |
| `tools/` | 工具实现 | [README](tools/README.md) |
