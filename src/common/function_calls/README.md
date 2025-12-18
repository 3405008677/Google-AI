# src/common/function_calls 目录

> 工具（Function Calling）注册中心，统一管理工具 Schema 与执行器。

---

## 核心能力

| 特性 | 说明 |
|:---|:---|
| **YAML Schema** | 工具定义存放在 `config.yaml`，自动转换为 OpenAI 格式 |
| **执行器注册** | 支持同步与异步执行器，按名称映射 |
| **Worker 权限** | 可按 Worker 粒度分配可用工具集 |
| **统一入口** | 通过 `get_tool()` / `execute_tool()` 访问所有能力 |

---

## 文件结构

```
function_calls/
├── __init__.py      # 导出便捷函数
├── config.yaml      # 工具 Schema 定义
└── registry.py      # ToolRegistry 单例实现
```

---

## 配置示例 (config.yaml)

```yaml
# 工具定义
tools:
  get_current_time:
    description: "获取当前日期和时间"
    parameters:
      type: object
      properties:
        timezone:
          type: string
          description: "时区，如 Asia/Shanghai"
      required: []

  web_search:
    description: "搜索互联网获取最新信息"
    parameters:
      type: object
      properties:
        query:
          type: string
          description: "搜索关键词"
      required: ["query"]

# Worker 可用工具映射
worker_tools:
  General:
    - get_current_time
  Search:
    - web_search
    - get_current_time
```

---

## API 参考

```python
from src.common.function_calls import (
    get_tool,           # 获取单个工具 Schema
    get_tools,          # 获取多个工具 Schema
    list_tools,         # 列出所有工具名
    get_worker_tools,   # 获取 Worker 可用工具
    execute_tool,       # 执行工具（同步）
    execute_tool_async, # 执行工具（异步）
)

# 获取工具定义（OpenAI function calling 格式）
tool = get_tool("get_current_time")
# 返回: {"type": "function", "function": {"name": "...", "description": "...", "parameters": {...}}}

# 获取 General Worker 的可用工具
tools = get_worker_tools("General")

# 执行工具
result = await execute_tool_async("get_current_time", {"timezone": "Asia/Shanghai"})
```

---

## 添加新工具

### 1. 定义 Schema

在 `config.yaml` 中添加：

```yaml
tools:
  my_new_tool:
    description: "工具描述"
    parameters:
      type: object
      properties:
        param1:
          type: string
          description: "参数说明"
      required: ["param1"]
```

### 2. 实现执行器

在 `src/tools/` 中创建实现文件：

```python
# src/tools/my_tool.py
def invoke(param1: str) -> str:
    return f"处理结果: {param1}"

async def ainvoke(param1: str) -> str:
    return invoke(param1)
```

### 3. 注册执行器

在 `registry.py` 的初始化逻辑中添加注册：

```python
registry.register_executor("my_new_tool", my_tool.invoke, my_tool.ainvoke)
```

---

## 内置工具

| 工具名 | 说明 | 依赖 |
|:---|:---|:---|
| `get_current_time` | 获取当前日期时间 | 无 |
| `web_search` | Tavily 网页搜索 | 需配置 `TAVILY_API_KEY` |
