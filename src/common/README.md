# src/common 目录

> 跨模块可复用的通用能力层，提供提示词管理与工具调用基础设施。

---

## 设计理念

将与具体业务无关的"基础能力"集中管理：
- **避免重复**：提示词、工具定义不在各模块中重复维护。
- **统一接口**：上层模块（如 `router/agents`）只调用这里的 API，不关心底层实现。
- **易于测试**：独立模块便于单元测试与 Mock。

---

## 模块组成

```
common/
├── __init__.py          # 统一导出入口
├── prompts/             # 提示词配置与管理
│   ├── config.yaml      # 提示词定义
│   └── manager.py       # PromptManager 单例
└── function_calls/      # 工具注册与调用
    ├── config.yaml      # 工具 Schema 定义
    └── registry.py      # ToolRegistry 单例
```

---

## 快速使用

### 提示词管理

```python
from src.common import get_prompt, list_prompts

# 获取提示词（支持点号路径）
system_prompt = get_prompt("workers.general.system")

# 带变量替换
prompt = get_prompt("greeting", name="Alice")

# 列出所有可用提示词
all_keys = list_prompts()
```

### 工具调用

```python
from src.common import get_tool, get_tools, list_tools

# 获取单个工具定义（OpenAI function calling 格式）
tool = get_tool("get_current_time")

# 获取多个工具
tools = get_tools(["get_current_time", "web_search"])

# 列出所有工具
all_tools = list_tools()
```

---

## 子目录文档

- [prompts/README.md](prompts/README.md) - 提示词管理详解
- [function_calls/README.md](function_calls/README.md) - 工具注册详解
