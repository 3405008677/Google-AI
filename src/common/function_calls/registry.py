"""
工具註冊表

提供工具的註冊、發現和執行功能。
"""

import yaml
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable, Union
from dataclasses import dataclass
from abc import ABC, abstractmethod

from src.server.logging_setup import logger


@dataclass
class ToolSchema:
    """工具 Schema 定義"""
    name: str
    description: str
    parameters: Dict[str, Any]
    implementation: Optional[Dict[str, str]] = None
    
    def to_openai_format(self) -> Dict[str, Any]:
        """轉換為 OpenAI function calling 格式"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
    
    def to_langchain_format(self) -> Dict[str, Any]:
        """轉換為 LangChain 工具格式"""
        return {
            "type": "function",
            "function": self.to_openai_format(),
        }


class BaseToolExecutor(ABC):
    """工具執行器基類"""
    
    @abstractmethod
    def invoke(self, params: Dict[str, Any]) -> Any:
        """同步執行工具"""
        pass
    
    @abstractmethod
    async def ainvoke(self, params: Dict[str, Any]) -> Any:
        """異步執行工具"""
        pass


class ToolRegistry:
    """
    工具註冊表
    
    線程安全的單例模式，管理所有工具定義和執行器。
    """
    
    _instance: Optional["ToolRegistry"] = None
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
        初始化工具註冊表
        
        Args:
            config_path: 配置文件路徑，默認為 src/common/function_calls/config.yaml
        """
        if self._initialized:
            return
            
        self.config_path = config_path or Path(__file__).parent / "config.yaml"
        self._schemas: Dict[str, ToolSchema] = {}
        self._executors: Dict[str, BaseToolExecutor] = {}
        self._worker_tools: Dict[str, List[str]] = {}
        self._load_lock = threading.Lock()
        
        self._load_config()
        self._register_builtin_tools()
        self._initialized = True
        
        logger.info(f"✅ ToolRegistry 初始化完成，已加載 {len(self._schemas)} 個工具")
    
    def _load_config(self) -> None:
        """從配置文件加載工具定義"""
        with self._load_lock:
            try:
                if not self.config_path.exists():
                    logger.warning(f"工具配置文件不存在: {self.config_path}")
                    return
                
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
                
                # 加載工具定義
                tools_config = config.get("tools", {})
                for name, tool_def in tools_config.items():
                    schema = ToolSchema(
                        name=tool_def.get("name", name),
                        description=tool_def.get("description", ""),
                        parameters=tool_def.get("parameters", {}),
                        implementation=tool_def.get("implementation"),
                    )
                    self._schemas[name] = schema
                
                # 加載 Worker 工具配置
                self._worker_tools = config.get("worker_tools", {})
                
                logger.debug(f"工具配置已加載，包含 {len(self._schemas)} 個工具定義")
                
            except yaml.YAMLError as e:
                logger.error(f"工具配置文件格式錯誤: {e}")
            except Exception as e:
                logger.error(f"加載工具配置失敗: {e}")
    
    def _register_builtin_tools(self) -> None:
        """註冊內置工具執行器"""
        # 註冊時間日期工具
        try:
            from src.tools.datetime_tool import DateTimeTool
            
            class DateTimeExecutor(BaseToolExecutor):
                def __init__(self):
                    self._tool = DateTimeTool()
                
                def invoke(self, params: Dict[str, Any]) -> str:
                    return self._tool.invoke(params)
                
                async def ainvoke(self, params: Dict[str, Any]) -> str:
                    return await self._tool.ainvoke(params)
            
            self._executors["get_current_datetime"] = DateTimeExecutor()
            logger.debug("已註冊內置工具: get_current_datetime")
        except ImportError as e:
            logger.warning(f"無法加載時間日期工具: {e}")
        
        # 註冊 Tavily 搜索工具
        try:
            from src.tools.search import TavilySearchTool, is_tavily_configured
            
            if is_tavily_configured():
                class TavilyExecutor(BaseToolExecutor):
                    def __init__(self):
                        self._tool = TavilySearchTool()
                    
                    def invoke(self, params: Dict[str, Any]) -> str:
                        query = params.get("query", "")
                        return self._tool.invoke(query)
                    
                    async def ainvoke(self, params: Dict[str, Any]) -> str:
                        query = params.get("query", "")
                        return await self._tool.ainvoke(query)
                
                self._executors["tavily_search"] = TavilyExecutor()
                self._executors["web_search"] = TavilyExecutor()  # 別名
                logger.debug("已註冊內置工具: tavily_search, web_search")
        except ImportError as e:
            logger.warning(f"無法加載 Tavily 搜索工具: {e}")
    
    def reload(self) -> bool:
        """
        重新加載配置
        
        Returns:
            是否成功
        """
        try:
            self._schemas.clear()
            self._worker_tools.clear()
            self._load_config()
            logger.info("🔄 工具配置已重新加載")
            return True
        except Exception as e:
            logger.error(f"重新加載工具配置失敗: {e}")
            return False
    
    def register(
        self,
        name: str,
        schema: Union[ToolSchema, Dict[str, Any]],
        executor: Optional[BaseToolExecutor] = None,
    ) -> None:
        """
        註冊工具
        
        Args:
            name: 工具名稱
            schema: 工具 Schema（ToolSchema 實例或字典）
            executor: 工具執行器（可選）
        """
        if isinstance(schema, dict):
            schema = ToolSchema(
                name=schema.get("name", name),
                description=schema.get("description", ""),
                parameters=schema.get("parameters", {}),
                implementation=schema.get("implementation"),
            )
        
        self._schemas[name] = schema
        if executor:
            self._executors[name] = executor
        
        logger.info(f"已註冊工具: {name}")
    
    def get_schema(self, name: str) -> Optional[ToolSchema]:
        """獲取工具 Schema"""
        return self._schemas.get(name)
    
    def get_executor(self, name: str) -> Optional[BaseToolExecutor]:
        """獲取工具執行器"""
        return self._executors.get(name)
    
    def get_tool(self, name: str) -> Optional[Dict[str, Any]]:
        """
        獲取工具定義（OpenAI 格式）
        
        Args:
            name: 工具名稱
            
        Returns:
            工具定義字典
        """
        schema = self._schemas.get(name)
        return schema.to_openai_format() if schema else None
    
    def get_tools(self, names: List[str]) -> List[Dict[str, Any]]:
        """
        獲取多個工具定義
        
        Args:
            names: 工具名稱列表
            
        Returns:
            工具定義列表
        """
        result = []
        for name in names:
            tool = self.get_tool(name)
            if tool:
                result.append(tool)
            else:
                logger.warning(f"工具 '{name}' 不存在")
        return result
    
    def get_all_tools(self) -> Dict[str, Dict[str, Any]]:
        """獲取所有工具定義"""
        return {name: schema.to_openai_format() for name, schema in self._schemas.items()}
    
    def get_worker_tools(self, worker_name: str) -> List[Dict[str, Any]]:
        """
        獲取指定 Worker 的工具列表
        
        Args:
            worker_name: Worker 名稱
            
        Returns:
            工具定義列表
        """
        tool_names = self._worker_tools.get(worker_name, [])
        return self.get_tools(tool_names)
    
    def list_tools(self) -> List[str]:
        """列出所有工具名稱"""
        return list(self._schemas.keys())
    
    def to_langchain(self, names: List[str]) -> List[Dict[str, Any]]:
        """
        轉換為 LangChain 格式
        
        Args:
            names: 工具名稱列表
            
        Returns:
            LangChain 工具格式列表
        """
        result = []
        for name in names:
            schema = self._schemas.get(name)
            if schema:
                result.append(schema.to_langchain_format())
        return result


# === 模組級便捷函數 ===

_registry_instance: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """獲取工具註冊表實例（單例）"""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = ToolRegistry()
    return _registry_instance


def get_tool(name: str) -> Optional[Dict[str, Any]]:
    """獲取工具定義"""
    return get_tool_registry().get_tool(name)


def get_tools(names: List[str]) -> List[Dict[str, Any]]:
    """獲取多個工具定義"""
    return get_tool_registry().get_tools(names)


def get_all_tools() -> Dict[str, Dict[str, Any]]:
    """獲取所有工具定義"""
    return get_tool_registry().get_all_tools()


def get_worker_tools(worker_name: str) -> List[Dict[str, Any]]:
    """獲取指定 Worker 的工具列表"""
    return get_tool_registry().get_worker_tools(worker_name)


def list_tools() -> List[str]:
    """列出所有工具名稱"""
    return get_tool_registry().list_tools()


def get_tools_for_langchain(names: List[str]) -> List[Dict[str, Any]]:
    """獲取 LangChain 格式的工具定義"""
    return get_tool_registry().to_langchain(names)


def get_tool_executor(name: str) -> Optional[BaseToolExecutor]:
    """獲取工具執行器"""
    return get_tool_registry().get_executor(name)


def register_tool(
    name: str,
    schema: Union[ToolSchema, Dict[str, Any]],
    executor: Optional[BaseToolExecutor] = None,
) -> None:
    """註冊工具"""
    get_tool_registry().register(name, schema, executor)


def reload_tools() -> bool:
    """重新加載工具配置"""
    return get_tool_registry().reload()

