"""
提示詞與工具管理模組（向後兼容層）

此模組保持向後兼容，實際實現已移至 src/common/prompts 和 src/common/function_calls。

推薦使用新的導入路徑：
    from src.common.prompts import get_prompt, reload_prompts
    from src.common.function_calls import get_tool, get_tools
"""

# 從公共模組重新導出提示詞相關函數
from src.common.prompts import (
    PromptManager,
    get_prompt_manager,
    get_prompt,
    reload_prompts,
    list_prompts,
    has_prompt,
)

# 從公共模組重新導出工具相關函數
from src.common.function_calls import (
    get_tool,
    get_tools,
    get_all_tools,
    get_worker_tools,
    list_tools,
    get_tools_for_langchain,
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
    "get_tool",
    "get_tools",
    "get_all_tools",
    "get_worker_tools",
    "list_tools",
    "get_tools_for_langchain",
]
