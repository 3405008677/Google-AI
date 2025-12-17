"""
统一 Function Call 工具管理模组

提供集中化的工具定义和管理，支持：
1. YAML 配置文件定义工具 Schema
2. 工具注册和发现
3. LangChain 格式转换
4. 工具执行器管理

使用方式：
    from src.common.function_calls import (
        get_tool,
        get_tools,
        get_tool_executor,
        register_tool,
    )
    
    # 获取单个工具定义
    tool = get_tool("get_current_datetime")
    
    # 获取多个工具定义
    tools = get_tools(["get_current_datetime", "web_search"])
    
    # 获取工具执行器
    executor = get_tool_executor("get_current_datetime")
    result = await executor.ainvoke({"timezone": "Asia/Shanghai"})
    
    # 注册自定义工具
    register_tool("my_tool", schema, executor)
"""

from src.common.function_calls.registry import (
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

