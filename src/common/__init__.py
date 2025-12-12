"""
公共模組

提供跨專案共享的功能：
1. prompts - 統一提示詞管理
2. function_calls - 統一 Function Call 工具管理

目錄結構：
    src/common/
    ├── __init__.py
    ├── prompts/
    │   ├── __init__.py
    │   ├── manager.py      # 提示詞管理器
    │   └── config.yaml     # 提示詞配置
    └── function_calls/
        ├── __init__.py
        ├── registry.py     # 工具註冊表
        └── config.yaml     # 工具配置

使用方式：
    # 獲取提示詞
    from src.common.prompts import get_prompt
    prompt = get_prompt("supervisor.planning", worker_list="...", max_steps=8)
    
    # 獲取工具定義
    from src.common.function_calls import get_tool, get_tools
    tool = get_tool("get_current_datetime")
    tools = get_tools(["web_search", "calculator"])
    
    # 獲取工具執行器
    from src.common.function_calls import get_tool_executor
    executor = get_tool_executor("get_current_datetime")
    result = executor.invoke({"timezone": "Asia/Shanghai"})
"""

# 提示詞管理
from src.common.prompts import (
    PromptManager,
    get_prompt_manager,
    get_prompt,
    reload_prompts,
    list_prompts,
    has_prompt,
)

# 工具管理
from src.common.function_calls import (
    ToolRegistry,
    get_tool_registry,
    get_tool,
    get_tools,
    get_all_tools,
    get_worker_tools,
    list_tools,
    get_tools_for_langchain,
    get_tool_executor,
    register_tool,
    reload_tools,
)

__all__ = [
    # 提示詞管理
    "PromptManager",
    "get_prompt_manager",
    "get_prompt",
    "reload_prompts",
    "list_prompts",
    "has_prompt",
    # 工具管理
    "ToolRegistry",
    "get_tool_registry",
    "get_tool",
    "get_tools",
    "get_all_tools",
    "get_worker_tools",
    "list_tools",
    "get_tools_for_langchain",
    "get_tool_executor",
    "register_tool",
    "reload_tools",
]
