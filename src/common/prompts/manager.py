"""
提示詞管理器

提供線程安全的提示詞加載和訪問。
支持 YAML 配置文件和熱加載。
"""

import yaml
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List

from src.server.logging_setup import logger


class SafeDict(dict):
    """
    安全字典，用於 format_map
    
    未提供的 key 會返回原始佔位符 {key}
    """
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


class PromptManager:
    """
    提示詞管理器
    
    線程安全的單例模式，管理所有提示詞配置。
    """
    
    _instance: Optional["PromptManager"] = None
    _lock = threading.Lock()
    
    def __new__(cls, config_path: Optional[Path] = None):
        """單例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        初始化提示詞管理器
        
        Args:
            config_path: 配置文件路徑，默認為 src/common/prompts/config.yaml
        """
        if self._initialized:
            return
            
        self.config_path = config_path or Path(__file__).parent / "config.yaml"
        self._cache: Dict[str, Any] = {}
        self._load_lock = threading.Lock()
        self._load()
        self._initialized = True
        
        logger.info(f"✅ PromptManager 初始化完成，配置文件: {self.config_path}")
    
    def _load(self) -> None:
        """
        加載配置文件
        
        線程安全的配置加載。
        """
        with self._load_lock:
            try:
                if not self.config_path.exists():
                    logger.warning(f"提示詞配置文件不存在: {self.config_path}")
                    self._cache = {}
                    return
                
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self._cache = yaml.safe_load(f) or {}
                
                logger.debug(f"提示詞配置已加載，包含 {len(self._cache)} 個頂級配置項")
                
            except yaml.YAMLError as e:
                logger.error(f"提示詞配置文件格式錯誤: {e}")
                self._cache = {}
            except Exception as e:
                logger.error(f"加載提示詞配置失敗: {e}")
                self._cache = {}
    
    def reload(self) -> bool:
        """
        熱加載配置文件
        
        Returns:
            是否加載成功
        """
        try:
            self._load()
            logger.info("🔄 提示詞配置已重新加載")
            return True
        except Exception as e:
            logger.error(f"重新加載提示詞配置失敗: {e}")
            return False
    
    def get(self, key: str, default: str = "", **format_kwargs) -> str:
        """
        獲取提示詞
        
        支持點號路徑訪問，如 "workers.researcher.system"
        支持模板變量替換，如 {worker_list}
        
        Args:
            key: 提示詞路徑，使用點號分隔
            default: 默認值（當路徑不存在時返回）
            **format_kwargs: 模板變量（可選）
            
        Returns:
            提示詞內容
        """
        keys = key.split(".")
        value: Any = self._cache
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        
        if not isinstance(value, str):
            return default
        
        # 如果有模板變量，進行替換
        if format_kwargs:
            try:
                value = value.format_map(SafeDict(format_kwargs))
            except Exception as e:
                logger.warning(f"提示詞模板替換失敗 [{key}]: {e}")
        
        return value
    
    def get_section(self, key: str) -> Dict[str, Any]:
        """
        獲取配置的一個部分（字典）
        
        Args:
            key: 配置路徑
            
        Returns:
            配置字典，如果不存在則返回空字典
        """
        keys = key.split(".")
        value: Any = self._cache
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return {}
            else:
                return {}
        
        return value if isinstance(value, dict) else {}
    
    def has(self, key: str) -> bool:
        """
        檢查提示詞是否存在
        
        Args:
            key: 提示詞路徑
            
        Returns:
            是否存在
        """
        keys = key.split(".")
        value: Any = self._cache
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return False
        
        return True
    
    def list_keys(self, prefix: str = "") -> List[str]:
        """
        列出所有可用的提示詞路徑
        
        Args:
            prefix: 路徑前綴過濾
            
        Returns:
            提示詞路徑列表
        """
        def _collect_keys(d: Dict, parent: str = "") -> List[str]:
            keys = []
            for k, v in d.items():
                full_key = f"{parent}.{k}" if parent else k
                if isinstance(v, dict):
                    keys.extend(_collect_keys(v, full_key))
                elif isinstance(v, str):
                    keys.append(full_key)
            return keys
        
        all_keys = _collect_keys(self._cache)
        
        if prefix:
            return [k for k in all_keys if k.startswith(prefix)]
        return all_keys


# === 模組級便捷函數 ===

_manager_instance: Optional[PromptManager] = None


def get_prompt_manager() -> PromptManager:
    """
    獲取提示詞管理器實例（單例）
    
    Returns:
        PromptManager 實例
    """
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = PromptManager()
    return _manager_instance


def get_prompt(key: str, default: str = "", **format_kwargs) -> str:
    """
    獲取提示詞（便捷函數）
    
    Args:
        key: 提示詞路徑，如 "workers.researcher.system"
        default: 默認值
        **format_kwargs: 模板變量
        
    Returns:
        提示詞內容
    """
    return get_prompt_manager().get(key, default, **format_kwargs)


def reload_prompts() -> bool:
    """
    重新加載提示詞配置（熱加載）
    
    Returns:
        是否成功
    """
    return get_prompt_manager().reload()


def list_prompts(prefix: str = "") -> List[str]:
    """
    列出所有可用的提示詞路徑
    
    Args:
        prefix: 路徑前綴過濾，如 "workers"
        
    Returns:
        提示詞路徑列表
    """
    return get_prompt_manager().list_keys(prefix)


def has_prompt(key: str) -> bool:
    """
    檢查提示詞是否存在
    
    Args:
        key: 提示詞路徑
        
    Returns:
        是否存在
    """
    return get_prompt_manager().has(key)

