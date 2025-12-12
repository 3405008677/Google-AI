## src/router/agents/supervisor 目录说明

## 概述
该目录实现 Supervisor Architecture：将用户复杂请求拆解为可执行步骤，并调度多个 Worker 完成任务。

## 关键组成
- `service.py`：对外统一服务入口（支持非流式与 SSE 流式），并可集成 Performance Layer。
- `workflow.py`：LangGraph 工作流构建与获取入口。
- `state.py`：Supervisor 状态结构（消息、任务计划、用户上下文等）。
- `registry.py`：Worker 注册表与注册/统计能力。
- `llm_factory.py`：模型/LLM 创建与选择（按配置构建）。
- `worker.py`：Worker 结构与执行封装。

## 典型调用链
路由层（`agents/api.py`） -> 依赖注入（`core/dependencies.py`） -> `SupervisorService` -> `workflow` 执行。
