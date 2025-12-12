"""
統一提示詞管理模組

提供集中化的提示詞管理，支持：
1. YAML 配置文件存儲
2. 點號路徑訪問 (如 "supervisor.planning")
3. 熱加載（不重啟服務更新配置）
4. 模板變量支持
5. 分類管理（supervisor、workers、system 等）

使用方式：
    from src.common.prompts import get_prompt, reload_prompts
    
    # 獲取提示詞
    prompt = get_prompt("supervisor.planning")
    
    # 帶模板變量
    prompt = get_prompt(
        "supervisor.planning",
        worker_list="...",
        max_steps=8
    )
    
    # 熱加載
    reload_prompts()
"""

from src.common.prompts.manager import (
    PromptManager,
    get_prompt_manager,
    get_prompt,
    reload_prompts,
    list_prompts,
    has_prompt,
)

__all__ = [
    "PromptManager",
    "get_prompt_manager",
    "get_prompt",
    "reload_prompts",
    "list_prompts",
    "has_prompt",
]

