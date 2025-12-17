"""
搜索工具模组

提供联网搜索功能，主要使用 Tavily API。

Tavily 是专为 AI 代理设计的搜索引擎，提供：
- 优化的搜索结果（AI 友好格式）
- 自动摘要
- 新闻和实时信息

使用方式：
    from src.tools.search import search_web, get_tavily_search
    
    # 方式 1：直接搜索
    results = await search_web("2024年诺贝尔物理学奖")
    
    # 方式 2：获取工具实例（用于 LangChain）
    tool = get_tavily_search()
    results = await tool.ainvoke("AI 最新发展")
"""

import asyncio
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass

from src.core.settings import settings
from src.server.logging_setup import logger


@dataclass
class SearchResult:
    """搜索结果"""
    title: str
    url: str
    content: str
    score: float = 0.0
    
    def __str__(self) -> str:
        return f"**{self.title}**\n{self.content}\n来源: {self.url}"


@dataclass
class SearchResponse:
    """搜索响应"""
    query: str
    answer: Optional[str]  # Tavily 的 AI 摘要
    results: List[SearchResult]
    
    def to_text(self) -> str:
        """转换为文本格式"""
        parts = []
        
        if self.answer:
            parts.append(f"📌 AI 摘要：\n{self.answer}\n")
        
        if self.results:
            parts.append("📚 搜索结果：")
            for i, result in enumerate(self.results, 1):
                parts.append(f"\n{i}. {result}")
        
        return "\n".join(parts) if parts else "未找到相关结果"


class TavilySearchTool:
    """
    Tavily 搜索工具
    
    封装 Tavily API，提供异步搜索功能。
    支持 LangChain 工具调用格式。
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        max_results: int = 5,
        search_depth: str = "basic",
        include_answer: bool = True,
        include_raw_content: bool = False,
        include_images: bool = False,
    ):
        """
        初始化 Tavily 搜索工具
        
        Args:
            api_key: Tavily API Key（默认从环境变量读取）
            max_results: 最大结果数量
            search_depth: 搜索深度 ("basic" 或 "advanced")
            include_answer: 是否包含 AI 摘要
            include_raw_content: 是否包含原始内容
            include_images: 是否包含图片
        """
        self.api_key = api_key or settings.tools.tavily.api_key
        self.max_results = max_results or settings.tools.tavily.max_results
        self.search_depth = search_depth or settings.tools.tavily.search_depth
        self.include_answer = include_answer
        self.include_raw_content = include_raw_content
        self.include_images = include_images
        
        self._client = None
    
    @property
    def is_configured(self) -> bool:
        """检查是否已配置 API Key"""
        return bool(self.api_key)
    
    def _get_client(self):
        """获取或创建 Tavily 客户端"""
        if self._client is None:
            if not self.api_key:
                raise ValueError("Tavily API Key 未配置，请设置 TAVILY_API_KEY 环境变量")
            
            try:
                from tavily import TavilyClient
                self._client = TavilyClient(api_key=self.api_key)
            except ImportError:
                raise ImportError("请安装 tavily-python: pip install tavily-python")
        
        return self._client
    
    def search(self, query: str) -> SearchResponse:
        """
        同步搜索
        
        Args:
            query: 搜索查询
            
        Returns:
            SearchResponse 搜索响应
        """
        client = self._get_client()
        
        try:
            logger.info(f"🔍 [Tavily] 正在搜索: {query[:50]}...")
            
            response = client.search(
                query=query,
                search_depth=self.search_depth,
                max_results=self.max_results,
                include_answer=self.include_answer,
                include_raw_content=self.include_raw_content,
                include_images=self.include_images,
            )
            
            # 解析结果
            results = [
                SearchResult(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    content=r.get("content", ""),
                    score=r.get("score", 0.0),
                )
                for r in response.get("results", [])
            ]
            
            logger.info(f"✅ [Tavily] 搜索完成，找到 {len(results)} 条结果")
            
            return SearchResponse(
                query=query,
                answer=response.get("answer"),
                results=results,
            )
            
        except Exception as e:
            logger.error(f"❌ [Tavily] 搜索失败: {e}")
            raise
    
    async def asearch(self, query: str) -> SearchResponse:
        """
        异步搜索
        
        Args:
            query: 搜索查询
            
        Returns:
            SearchResponse 搜索响应
        """
        # Tavily 目前没有原生异步支持，使用线程池
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.search, query)
    
    # LangChain 兼容接口
    async def ainvoke(self, query: Union[str, Dict[str, Any]]) -> str:
        """
        LangChain 异步调用接口
        
        Args:
            query: 搜索查询（字符串或字典）
            
        Returns:
            搜索结果文本
        """
        if isinstance(query, dict):
            query = query.get("query", str(query))
        
        response = await self.asearch(query)
        return response.to_text()
    
    def invoke(self, query: Union[str, Dict[str, Any]]) -> str:
        """
        LangChain 同步调用接口
        
        Args:
            query: 搜索查询（字符串或字典）
            
        Returns:
            搜索结果文本
        """
        if isinstance(query, dict):
            query = query.get("query", str(query))
        
        response = self.search(query)
        return response.to_text()
    
    def __repr__(self) -> str:
        return f"TavilySearchTool(configured={self.is_configured}, max_results={self.max_results})"


# === 全局实例和便捷函数 ===

_tavily_instance: Optional[TavilySearchTool] = None


def get_tavily_search(
    max_results: Optional[int] = None,
    search_depth: Optional[str] = None,
) -> TavilySearchTool:
    """
    获取 Tavily 搜索工具实例
    
    Args:
        max_results: 覆盖默认的最大结果数量
        search_depth: 覆盖默认的搜索深度
        
    Returns:
        TavilySearchTool 实例
        
    Examples:
        # 使用默认配置
        tool = get_tavily_search()
        
        # 自定义配置
        tool = get_tavily_search(max_results=10, search_depth="advanced")
    """
    global _tavily_instance
    
    # 如果有自定义参数，创建新实例
    if max_results is not None or search_depth is not None:
        return TavilySearchTool(
            max_results=max_results or settings.tools.tavily.max_results,
            search_depth=search_depth or settings.tools.tavily.search_depth,
        )
    
    # 否则使用单例
    if _tavily_instance is None:
        _tavily_instance = TavilySearchTool()
    
    return _tavily_instance


def is_tavily_configured() -> bool:
    """
    检查 Tavily 是否已配置
    
    Returns:
        是否已配置 API Key
    """
    return settings.tools.tavily.is_configured()


async def search_web(
    query: str,
    max_results: int = 5,
    include_answer: bool = True,
) -> str:
    """
    执行 Web 搜索（便捷函数）
    
    Args:
        query: 搜索查询
        max_results: 最大结果数量
        include_answer: 是否包含 AI 摘要
        
    Returns:
        格式化的搜索结果文本
        
    Examples:
        results = await search_web("最新 AI 技术发展")
        print(results)
        
    Raises:
        ValueError: 如果 Tavily 未配置
    """
    if not is_tavily_configured():
        logger.warning("⚠️ Tavily 未配置，返回模拟搜索结果")
        return f"关于 '{query}' 的搜索结果：[Tavily 未配置，请设置 TAVILY_API_KEY 环境变量]"
    
    tool = TavilySearchTool(
        max_results=max_results,
        include_answer=include_answer,
    )
    
    return await tool.ainvoke(query)

