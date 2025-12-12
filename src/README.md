## src 目录说明

## 概述
此目录为项目的核心源码区，包含服务启动入口、FastAPI 应用组装、路由系统、Agent/Supervisor 架构、工具与配置。

## 运行入口
- `src/main.py`：项目主入口，读取配置并启动 Uvicorn/FastAPI。

## 目录结构（高层）
- `server/`：FastAPI 应用创建、生命周期、日志、中间件、SSL 启动参数封装。
- `router/`：API 路由注册、中间件（认证/限流/追踪）、健康检查、Agent 路由、授权服务。
- `core/`：依赖注入、统一配置中心（dataclass）、指标与核心异常。
- `common/`：通用能力（提示词管理、function calling 工具注册表等）。
- `tools/`：可被 LLM/Agent 调用的工具实现（如时间、搜索）。
- `prompts/`：预留/扩展的提示词资源目录。

## 配置说明
项目中同时存在两套配置入口：
- `src/config.py`：面向应用启动与模型连接的配置（`AppConfig` 等）。
- `src/core/settings.py`：统一配置中心（`settings`），更偏“全量配置聚合”。

通常通过 `.env` / 环境变量配置，例如：`PORT`、`DEBUG`、`ENABLE_ROUTER`、`GEMINI_API_KEY`、`QWEN_API_KEY` 等。
