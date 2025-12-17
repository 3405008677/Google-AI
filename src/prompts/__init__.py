"""
提示词与工具管理模组（向后兼容层）

此模组保持向后兼容，实际实现已移至 src/common/prompts 和 src/common/function_calls。

推荐使用新的导入路径：
    from src.common.prompts import get_prompt, reload_prompts
    from src.common.function_calls import get_tool, get_tools
"""

# 从公共模组重新导出提示词相关函数
from src.common.prompts import (
    PromptManager,
    get_prompt_manager,
    get_prompt,
    reload_prompts,
    list_prompts,
    has_prompt,
)

# 从公共模组重新导出工具相关函数
from src.common.function_calls import (
    get_tool,
    get_tools,
    get_all_tools,
    get_worker_tools,
    list_tools,
    get_tools_for_langchain,
)

__all__ = [
    # 提示词管理
    "PromptManager",
    "get_prompt_manager",
    "get_prompt",
    "reload_prompts",
    "list_prompts",
    "has_prompt",
    # 工具管理
    "get_tool",
    "get_tools",
    "get_all_tools",
    "get_worker_tools",
    "list_tools",
    "get_tools_for_langchain",
]
