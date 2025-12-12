"""
搜索工具模組

提供聯網搜索功能，主要使用 Tavily API。

Tavily 是專為 AI 代理設計的搜索引擎，提供：
- 優化的搜索結果（AI 友好格式）
- 自動摘要
- 新聞和實時信息

使用方式：
    from src.tools.search import search_web, get_tavily_search
    
    # 方式 1：直接搜索
    results = await search_web("2024年諾貝爾物理學獎")
    
    # 方式 2：獲取工具實例（用於 LangChain）
    tool = get_tavily_search()
    results = await tool.ainvoke("AI 最新發展")
"""

import asyncio
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass

from src.core.settings import settings
from src.server.logging_setup import logger


@dataclass
class SearchResult:
    """搜索結果"""
    title: str
    url: str
    content: str
    score: float = 0.0
    
    def __str__(self) -> str:
        return f"**{self.title}**\n{self.content}\n來源: {self.url}"


@dataclass
class SearchResponse:
    """搜索響應"""
    query: str
    answer: Optional[str]  # Tavily 的 AI 摘要
    results: List[SearchResult]
    
    def to_text(self) -> str:
        """轉換為文本格式"""
        parts = []
        
        if self.answer:
            parts.append(f"📌 AI 摘要：\n{self.answer}\n")
        
        if self.results:
            parts.append("📚 搜索結果：")
            for i, result in enumerate(self.results, 1):
                parts.append(f"\n{i}. {result}")
        
        return "\n".join(parts) if parts else "未找到相關結果"


class TavilySearchTool:
    """
    Tavily 搜索工具
    
    封裝 Tavily API，提供異步搜索功能。
    支持 LangChain 工具調用格式。
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
            api_key: Tavily API Key（默認從環境變量讀取）
            max_results: 最大結果數量
            search_depth: 搜索深度 ("basic" 或 "advanced")
            include_answer: 是否包含 AI 摘要
            include_raw_content: 是否包含原始內容
            include_images: 是否包含圖片
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
        """檢查是否已配置 API Key"""
        return bool(self.api_key)
    
    def _get_client(self):
        """獲取或創建 Tavily 客戶端"""
        if self._client is None:
            if not self.api_key:
                raise ValueError("Tavily API Key 未配置，請設置 TAVILY_API_KEY 環境變量")
            
            try:
                from tavily import TavilyClient
                self._client = TavilyClient(api_key=self.api_key)
            except ImportError:
                raise ImportError("請安裝 tavily-python: pip install tavily-python")
        
        return self._client
    
    def search(self, query: str) -> SearchResponse:
        """
        同步搜索
        
        Args:
            query: 搜索查詢
            
        Returns:
            SearchResponse 搜索響應
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
            
            # 解析結果
            results = [
                SearchResult(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    content=r.get("content", ""),
                    score=r.get("score", 0.0),
                )
                for r in response.get("results", [])
            ]
            
            logger.info(f"✅ [Tavily] 搜索完成，找到 {len(results)} 條結果")
            
            return SearchResponse(
                query=query,
                answer=response.get("answer"),
                results=results,
            )
            
        except Exception as e:
            logger.error(f"❌ [Tavily] 搜索失敗: {e}")
            raise
    
    async def asearch(self, query: str) -> SearchResponse:
        """
        異步搜索
        
        Args:
            query: 搜索查詢
            
        Returns:
            SearchResponse 搜索響應
        """
        # Tavily 目前沒有原生異步支持，使用線程池
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.search, query)
    
    # LangChain 兼容接口
    async def ainvoke(self, query: Union[str, Dict[str, Any]]) -> str:
        """
        LangChain 異步調用接口
        
        Args:
            query: 搜索查詢（字符串或字典）
            
        Returns:
            搜索結果文本
        """
        if isinstance(query, dict):
            query = query.get("query", str(query))
        
        response = await self.asearch(query)
        return response.to_text()
    
    def invoke(self, query: Union[str, Dict[str, Any]]) -> str:
        """
        LangChain 同步調用接口
        
        Args:
            query: 搜索查詢（字符串或字典）
            
        Returns:
            搜索結果文本
        """
        if isinstance(query, dict):
            query = query.get("query", str(query))
        
        response = self.search(query)
        return response.to_text()
    
    def __repr__(self) -> str:
        return f"TavilySearchTool(configured={self.is_configured}, max_results={self.max_results})"


# === 全局實例和便捷函數 ===

_tavily_instance: Optional[TavilySearchTool] = None


def get_tavily_search(
    max_results: Optional[int] = None,
    search_depth: Optional[str] = None,
) -> TavilySearchTool:
    """
    獲取 Tavily 搜索工具實例
    
    Args:
        max_results: 覆蓋默認的最大結果數量
        search_depth: 覆蓋默認的搜索深度
        
    Returns:
        TavilySearchTool 實例
        
    Examples:
        # 使用默認配置
        tool = get_tavily_search()
        
        # 自定義配置
        tool = get_tavily_search(max_results=10, search_depth="advanced")
    """
    global _tavily_instance
    
    # 如果有自定義參數，創建新實例
    if max_results is not None or search_depth is not None:
        return TavilySearchTool(
            max_results=max_results or settings.tools.tavily.max_results,
            search_depth=search_depth or settings.tools.tavily.search_depth,
        )
    
    # 否則使用單例
    if _tavily_instance is None:
        _tavily_instance = TavilySearchTool()
    
    return _tavily_instance


def is_tavily_configured() -> bool:
    """
    檢查 Tavily 是否已配置
    
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
    執行 Web 搜索（便捷函數）
    
    Args:
        query: 搜索查詢
        max_results: 最大結果數量
        include_answer: 是否包含 AI 摘要
        
    Returns:
        格式化的搜索結果文本
        
    Examples:
        results = await search_web("最新 AI 技術發展")
        print(results)
        
    Raises:
        ValueError: 如果 Tavily 未配置
    """
    if not is_tavily_configured():
        logger.warning("⚠️ Tavily 未配置，返回模擬搜索結果")
        return f"關於 '{query}' 的搜索結果：[Tavily 未配置，請設置 TAVILY_API_KEY 環境變量]"
    
    tool = TavilySearchTool(
        max_results=max_results,
        include_answer=include_answer,
    )
    
    return await tool.ainvoke(query)

