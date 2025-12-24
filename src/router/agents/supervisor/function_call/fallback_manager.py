"""
Function Call 降级方案管理器

当模型不支持 Function Calling 时，统一管理所有降级方案。
支持多种类型的降级：时间、搜索、数据查询等。
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from src.server.logging_setup import logger

from .fallback import get_current_datetime_fallback


@dataclass
class FallbackInfo:
    """降级方案信息"""
    name: str  # 降级方案名称，如 "datetime", "search", "data_query"
    description: str  # 描述
    get_info: Callable[..., str]  # 获取降级信息的函数
    prompt_key: Optional[str] = None  # 对应的 prompt 模板键（如果使用单独的模板）


class FallbackManager:
    """
    降级方案管理器
    
    统一管理所有 Function Call 降级方案，支持动态注册和收集。
    """
    
    def __init__(self):
        self._fallbacks: Dict[str, FallbackInfo] = {}
        self._register_default_fallbacks()
    
    def _register_default_fallbacks(self):
        """注册默认的降级方案"""
        self.register(
            name="datetime",
            description="时间日期信息降级方案",
            get_info=lambda timezone="Asia/Shanghai": get_current_datetime_fallback(timezone),
            prompt_key="workers.general.system_with_datetime",
        )
    
    def register(
        self,
        name: str,
        description: str,
        get_info: Callable[..., str],
        prompt_key: Optional[str] = None,
    ):
        """
        注册降级方案
        
        Args:
            name: 降级方案名称
            description: 描述
            get_info: 获取降级信息的函数
            prompt_key: 对应的 prompt 模板键
        """
        self._fallbacks[name] = FallbackInfo(
            name=name,
            description=description,
            get_info=get_info,
            prompt_key=prompt_key,
        )
        logger.debug(f"注册降级方案: {name} - {description}")
    
    def get_fallback_info(self, name: str, **kwargs) -> Optional[str]:
        """
        获取指定降级方案的信息
        
        Args:
            name: 降级方案名称
            **kwargs: 传递给 get_info 函数的参数
            
        Returns:
            降级信息字符串，如果方案不存在则返回 None
        """
        fallback = self._fallbacks.get(name)
        if not fallback:
            logger.warning(f"降级方案 '{name}' 未注册")
            return None
        
        try:
            return fallback.get_info(**kwargs)
        except Exception as e:
            logger.error(f"获取降级方案 '{name}' 信息失败: {e}", exc_info=True)
            return None
    
    def collect_fallback_info(
        self,
        fallback_names: List[str],
        **kwargs
    ) -> Dict[str, str]:
        """
        收集多个降级方案的信息
        
        Args:
            fallback_names: 需要收集的降级方案名称列表
            **kwargs: 传递给各个 get_info 函数的参数（会按名称传递）
            
        Returns:
            降级信息字典，键为方案名称，值为信息字符串
        """
        results = {}
        for name in fallback_names:
            # 尝试从 kwargs 中提取该方案特定的参数
            # 例如：datetime_timezone, search_query 等
            fallback_kwargs = {}
            for key, value in kwargs.items():
                if key.startswith(f"{name}_"):
                    # 提取参数名（去掉前缀）
                    param_name = key[len(f"{name}_"):]
                    fallback_kwargs[param_name] = value
                elif key == name or key in ["timezone", "language"]:  # 通用参数
                    fallback_kwargs[key] = value
            
            info = self.get_fallback_info(name, **fallback_kwargs)
            if info:
                results[name] = info
        
        return results
    
    def build_system_prompt_with_fallbacks(
        self,
        base_prompt_key: str,
        fallback_names: List[str],
        fallback_info: Dict[str, str],
        **extra_kwargs
    ) -> str:
        """
        构建包含降级信息的系统提示词
        
        Args:
            base_prompt_key: 基础 prompt 模板键
            fallback_names: 使用的降级方案名称列表
            fallback_info: 降级信息字典
            **extra_kwargs: 额外的 prompt 参数（如 language）
            
        Returns:
            构建好的系统提示词
        """
        from src.common.prompts import get_prompt
        
        # 如果只有一个降级方案且它有专门的 prompt_key，使用专门的模板
        if len(fallback_names) == 1:
            fallback = self._fallbacks.get(fallback_names[0])
            if fallback and fallback.prompt_key:
                prompt_key = fallback.prompt_key
                # 将降级信息作为参数传递
                # 对于 datetime，使用 datetime_info 作为参数名（与现有 prompt 模板保持一致）
                info_value = fallback_info.get(fallback_names[0], "")
                if fallback_names[0] == "datetime":
                    param_name = "datetime_info"
                else:
                    param_name = f"{fallback_names[0]}_info"
                return get_prompt(
                    prompt_key,
                    **{param_name: info_value},
                    **extra_kwargs
                )
        
        # 多个降级方案或使用通用模板
        # 将所有降级信息合并到 extra_kwargs 中
        prompt_kwargs = {**extra_kwargs}
        for name, info in fallback_info.items():
            prompt_kwargs[f"{name}_info"] = info
        
        # 尝试使用带 fallback 的模板，如果不存在则使用基础模板
        fallback_prompt_key = f"{base_prompt_key}_with_fallbacks"
        try:
            return get_prompt(fallback_prompt_key, **prompt_kwargs)
        except:
            # 如果专门的模板不存在，使用基础模板
            logger.debug(f"未找到模板 '{fallback_prompt_key}'，使用基础模板 '{base_prompt_key}'")
            return get_prompt(base_prompt_key, **prompt_kwargs)


# 全局单例
_fallback_manager: Optional[FallbackManager] = None


def get_fallback_manager() -> FallbackManager:
    """获取降级方案管理器单例"""
    global _fallback_manager
    if _fallback_manager is None:
        _fallback_manager = FallbackManager()
    return _fallback_manager

