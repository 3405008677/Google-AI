"""
统一提示词管理模组

提供集中化的提示词管理，支持：
1. YAML 多文件配置（按功能模块拆分）
2. 点号路径访问 (如 "supervisor.planning.system")
3. 热加载（不重启服务更新配置）
4. 模板变量支持
5. 分类管理（supervisor、workers、system 等）

使用方式：
    from src.common.prompts import get_prompt, reload_prompts
    
    # 获取提示词
    prompt = get_prompt("supervisor.planning.system")
    
    # 带模板变量
    prompt = get_prompt(
        "supervisor.planning.system",
        worker_list="...",
        max_steps=8
    )
    
    # 热加载
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

