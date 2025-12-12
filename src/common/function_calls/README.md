## src/common/function_calls 目录说明

## 概述
该目录提供 function calling（工具调用）相关能力：
- 从 `config.yaml` 加载工具定义（Schema）
- 管理工具执行器（同步/异步）
- 向上层提供统一的获取/列举/执行入口

## 关键文件
- `config.yaml`：工具定义与 Worker 可用工具映射配置。
- `registry.py`：`ToolRegistry` 单例与工具 Schema/执行器注册逻辑。

## 常用用法
- 获取工具定义（OpenAI function calling 格式）：`get_tool(name)` / `get_tools(names)`
- 列出可用工具：`list_tools()`
- 获取指定 Worker 可用工具：`get_worker_tools(worker_name)`

## 备注
内置工具执行器包含：时间日期工具、Tavily 搜索工具（需配置后启用）。
