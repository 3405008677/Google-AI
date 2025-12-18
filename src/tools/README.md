# src/tools 目录

> 可被 Agent/LLM 调用的工具实现层。

---

## 设计原则

1. **单一职责**：每个工具文件实现一个具体能力。
2. **双入口**：同时提供 `invoke`（同步）和 `ainvoke`（异步）。
3. **Schema 分离**：工具定义在 `common/function_calls/config.yaml`，实现在这里。

---

## 文件结构

```
tools/
├── __init__.py        # 导出工具函数
├── datetime_tool.py   # 时间日期工具
└── search.py          # 网页搜索工具
```

---

## 内置工具

### 1. datetime_tool.py

获取当前日期时间，支持时区参数。

```python
from src.tools.datetime_tool import invoke, ainvoke

# 同步调用
result = invoke(timezone="Asia/Shanghai")
# 返回: "2024-01-15 14:30:00 CST"

# 异步调用
result = await ainvoke(timezone="UTC")
```

### 2. search.py

基于 Tavily API 的网页搜索。

```python
from src.tools.search import ainvoke

result = await ainvoke(query="Python 最新版本")
# 返回搜索结果摘要
```

**配置要求**：
```ini
TAVILY_API_KEY=your_api_key
```

---

## 添加新工具

### 步骤 1：创建实现文件

```python
# src/tools/my_tool.py

def invoke(param1: str, param2: int = 10) -> str:
    """
    工具的同步实现
    
    Args:
        param1: 参数说明
        param2: 可选参数
    
    Returns:
        处理结果
    """
    return f"结果: {param1}, {param2}"

async def ainvoke(param1: str, param2: int = 10) -> str:
    """工具的异步实现"""
    # 如果有 IO 操作，使用 async 版本
    return invoke(param1, param2)
```

### 步骤 2：定义 Schema

在 `src/common/function_calls/config.yaml` 中添加：

```yaml
tools:
  my_tool:
    description: "工具功能描述"
    parameters:
      type: object
      properties:
        param1:
          type: string
          description: "参数1说明"
        param2:
          type: integer
          description: "参数2说明"
          default: 10
      required: ["param1"]
```

### 步骤 3：注册执行器

在 `src/common/function_calls/registry.py` 中注册：

```python
from src.tools import my_tool

registry.register_executor(
    "my_tool",
    sync_executor=my_tool.invoke,
    async_executor=my_tool.ainvoke,
)
```

---

## 最佳实践

- **错误处理**：工具内部捕获异常，返回友好错误信息。
- **超时控制**：外部 API 调用设置合理超时。
- **日志记录**：关键操作记录日志，便于排查。
- **幂等性**：尽可能保证工具调用的幂等性。
