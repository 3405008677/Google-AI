"""
提示词管理器

提供线程安全的提示词加载和访问。
支持 YAML 配置文件、多文件夹结构和热加载。
"""

import yaml
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List

from src.server.logging_setup import logger


class SafeDict(dict):
    """
    安全字典，用于 format_map
    
    未提供的 key 会返回原始占位符 {key}
    """
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def deep_merge(base: Dict, override: Dict) -> Dict:
    """
    深度合并两个字典
    
    Args:
        base: 基础字典
        override: 覆盖字典（优先级更高）
        
    Returns:
        合并后的字典
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class PromptManager:
    """
    提示词管理器
    
    线程安全的单例模式，管理所有提示词配置。
    支持多文件和文件夹结构。
    """
    
    _instance: Optional["PromptManager"] = None
    _lock = threading.Lock()
    
    # 定义文件夹结构映射（文件夹名 -> 配置前缀）
    FOLDER_MAPPINGS = {
        "supervisor": "supervisor",
        "workers": "workers", 
        "system": "system",
    }
    
    # 定义独立文件映射（文件名 -> 配置前缀）
    FILE_MAPPINGS = {
        "common.yaml": "common",
        "languages.yaml": "languages",
        "search.yaml": "search",
        "rules.yaml": "rules",
    }
    
    def __new__(cls, config_path: Optional[Path] = None):
        """单例模式"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        初始化提示词管理器
        
        Args:
            config_path: 配置目录路径，默认为 src/common/prompts/
        """
        if self._initialized:
            return
            
        self.config_dir = config_path or Path(__file__).parent
        self._cache: Dict[str, Any] = {}
        self._load_lock = threading.Lock()
        self._load()
        self._initialized = True
        
        logger.info(f"✅ PromptManager 初始化完成，配置目录: {self.config_dir}")
    
    def _load_yaml_file(self, file_path: Path) -> Dict[str, Any]:
        """
        加载单个 YAML 文件
        
        Args:
            file_path: YAML 文件路径
            
        Returns:
            解析后的字典
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            logger.error(f"YAML 格式错误 [{file_path}]: {e}")
            return {}
        except Exception as e:
            logger.error(f"加载文件失败 [{file_path}]: {e}")
            return {}
    
    def _load_folder(self, folder_path: Path, prefix: str) -> Dict[str, Any]:
        """
        加载文件夹中的所有 YAML 文件
        
        文件夹结构会映射为嵌套字典：
        - supervisor/planning.yaml -> supervisor.planning.*
        - supervisor/routing.yaml -> supervisor.routing.*
        
        Args:
            folder_path: 文件夹路径
            prefix: 配置前缀
            
        Returns:
            合并后的字典
        """
        result: Dict[str, Any] = {}
        
        if not folder_path.exists() or not folder_path.is_dir():
            return result
        
        for yaml_file in folder_path.glob("*.yaml"):
            # 文件名（不含扩展名）作为子键
            sub_key = yaml_file.stem
            file_content = self._load_yaml_file(yaml_file)
            
            if file_content:
                result[sub_key] = file_content
                logger.debug(f"加载配置: {prefix}.{sub_key} <- {yaml_file.name}")
        
        return result
    
    def _load(self) -> None:
        """
        加载所有配置文件
        
        支持两种模式：
        1. 多文件模式：从文件夹结构加载（supervisor/, workers/, system/, 等）
        2. 单文件模式（向后兼容）：从 config.yaml 加载
        
        线程安全的配置加载。
        """
        with self._load_lock:
            try:
                self._cache = {}
                loaded_count = 0
                
                # 1. 加载文件夹结构
                for folder_name, prefix in self.FOLDER_MAPPINGS.items():
                    folder_path = self.config_dir / folder_name
                    if folder_path.exists() and folder_path.is_dir():
                        folder_content = self._load_folder(folder_path, prefix)
                        if folder_content:
                            self._cache[prefix] = folder_content
                            loaded_count += len(folder_content)
                
                # 2. 加载独立文件
                for file_name, prefix in self.FILE_MAPPINGS.items():
                    file_path = self.config_dir / file_name
                    if file_path.exists():
                        file_content = self._load_yaml_file(file_path)
                        if file_content:
                            self._cache[prefix] = file_content
                            loaded_count += 1
                            logger.debug(f"加载配置: {prefix} <- {file_name}")
                
                # 3. 向后兼容：如果存在 config.yaml，合并其内容
                legacy_config = self.config_dir / "config.yaml"
                if legacy_config.exists():
                    legacy_content = self._load_yaml_file(legacy_config)
                    if legacy_content:
                        # 深度合并，文件夹内容优先级更高
                        self._cache = deep_merge(legacy_content, self._cache)
                        logger.debug(f"合并旧版配置: config.yaml")
                
                if loaded_count > 0:
                    logger.debug(f"提示词配置已加载，共 {len(self._cache)} 个顶级配置项")
                else:
                    logger.warning(f"未找到任何提示词配置文件: {self.config_dir}")
                
            except Exception as e:
                logger.error(f"加载提示词配置失败: {e}")
                self._cache = {}
    
    def reload(self) -> bool:
        """
        热加载配置文件
        
        Returns:
            是否加载成功
        """
        try:
            self._load()
            logger.info("🔄 提示词配置已重新加载")
            return True
        except Exception as e:
            logger.error(f"重新加载提示词配置失败: {e}")
            return False
    
    def _resolve_references(self, value: str, max_depth: int = 10) -> str:
        """
        解析引用语法 @path.to.prompt
        
        支持在提示词中引用其他提示词，实现组件复用。
        例如: @common.output_constraints.json_only
        
        Args:
            value: 包含引用的字符串
            max_depth: 最大递归深度（防止循环引用）
            
        Returns:
            解析后的字符串
        """
        import re
        
        if max_depth <= 0:
            logger.warning("提示词引用递归深度超限，可能存在循环引用")
            return value
        
        # 匹配 @path.to.prompt 格式（支持下划线和字母数字）
        pattern = r'@([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)'
        
        def replace_ref(match):
            ref_path = match.group(1)
            # 递归获取引用内容（不传 format_kwargs，避免重复替换）
            ref_value = self._get_raw(ref_path)
            if ref_value:
                # 递归解析嵌套引用
                return self._resolve_references(ref_value, max_depth - 1)
            else:
                logger.warning(f"提示词引用未找到: @{ref_path}")
                return match.group(0)  # 保留原样
        
        return re.sub(pattern, replace_ref, value)
    
    def _get_raw(self, key: str) -> Optional[str]:
        """
        获取原始提示词（不做模板替换）
        
        Args:
            key: 提示词路径
            
        Returns:
            原始提示词内容，不存在则返回 None
        """
        keys = key.split(".")
        value: Any = self._cache
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return None
            else:
                return None
        
        return value if isinstance(value, str) else None
    
    def get(self, key: str, default: str = "", **format_kwargs) -> str:
        """
        获取提示词
        
        支持点号路径访问，如 "workers.researcher.system"
        支持模板变量替换，如 {worker_list}
        支持引用语法，如 @common.output_constraints.json_only
        
        Args:
            key: 提示词路径，使用点号分隔
            default: 默认值（当路径不存在时返回）
            **format_kwargs: 模板变量（可选）
            
        Returns:
            提示词内容
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
        
        # 1. 先解析 @引用
        if '@' in value:
            value = self._resolve_references(value)
        
        # 2. 再进行模板变量替换
        if format_kwargs:
            try:
                value = value.format_map(SafeDict(format_kwargs))
            except Exception as e:
                logger.warning(f"提示词模板替换失败 [{key}]: {e}")
        
        return value
    
    def get_section(self, key: str) -> Dict[str, Any]:
        """
        获取配置的一个部分（字典）
        
        Args:
            key: 配置路径
            
        Returns:
            配置字典，如果不存在则返回空字典
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
        检查提示词是否存在
        
        Args:
            key: 提示词路径
            
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
        列出所有可用的提示词路径
        
        Args:
            prefix: 路径前缀过滤
            
        Returns:
            提示词路径列表
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


# === 模组级便捷函数 ===

_manager_instance: Optional[PromptManager] = None


def get_prompt_manager() -> PromptManager:
    """
    获取提示词管理器实例（单例）
    
    Returns:
        PromptManager 实例
    """
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = PromptManager()
    return _manager_instance


def get_prompt(key: str, default: str = "", **format_kwargs) -> str:
    """
    获取提示词（便捷函数）
    
    Args:
        key: 提示词路径，如 "workers.researcher.system"
        default: 默认值
        **format_kwargs: 模板变量
        
    Returns:
        提示词内容
    """
    return get_prompt_manager().get(key, default, **format_kwargs)


def reload_prompts() -> bool:
    """
    重新加载提示词配置（热加载）
    
    Returns:
        是否成功
    """
    return get_prompt_manager().reload()


def list_prompts(prefix: str = "") -> List[str]:
    """
    列出所有可用的提示词路径
    
    Args:
        prefix: 路径前缀过滤，如 "workers"
        
    Returns:
        提示词路径列表
    """
    return get_prompt_manager().list_keys(prefix)


def has_prompt(key: str) -> bool:
    """
    检查提示词是否存在
    
    Args:
        key: 提示词路径
        
    Returns:
        是否存在
    """
    return get_prompt_manager().has(key)

