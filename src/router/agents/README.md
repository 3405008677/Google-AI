## src/router/agents 目录说明

## 概述
该目录实现 Agent/Supervisor 架构，并对外提供相关 API：
- Supervisor：负责任务分解、调度与执行流程（LangGraph/LangChain）。
- Workers：负责执行具体子任务。
- Performance Layer：在进入昂贵 LLM 调用前的“速通”优化（规则引擎/语义缓存）。

## 关键入口
- `api.py`：对外的 Agent API 路由（支持非流式与 SSE 流式）。
- `supervisor/`：Supervisor 服务、状态、工作流与 Worker 注册。
- `performance_layer/`：语义缓存与规则引擎。
- `AI/`：模型提供方路由/适配（Customize/Qwen/Gemini）。
