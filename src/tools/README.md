## src/tools 目录说明

## 概述
该目录存放可被 Agent/LLM 调用的工具实现（tooling）。这些工具通常会被 `src/common/function_calls` 注册为 function calling 工具，并在工作流中按需调用。

## 当前工具
- `datetime_tool.py`：获取当前日期时间等能力。
- `search.py`：搜索工具（如 Tavily），用于联网检索（需配置后启用）。

## 约定
新增工具时建议：
- 提供同步 `invoke` 与异步 `ainvoke` 入口
- 在 `src/common/function_calls/registry.py` 中注册执行器（或通过配置加载）
