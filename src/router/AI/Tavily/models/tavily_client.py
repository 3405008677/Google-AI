"""
Tavily 搜索客户端

封装 Tavily API 的搜索功能。
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Dict, List, Optional

try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None
    logging.warning("tavily-python package not installed. Run: pip install tavily-python")

logger = logging.getLogger(__name__)


class TavilyClientError(RuntimeError):
    """Tavily 客户端错误"""


class TavilySearchClient:
    """Tavily 搜索客户端"""

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化 Tavily 客户端
        
        Args:
            api_key: Tavily API 密钥，如果不提供则从环境变量读取
        """
        if TavilyClient is None:
            raise TavilyClientError(
                "tavily-python package not installed. Please install it with: pip install tavily-python"
            )

        api_key = api_key or os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise TavilyClientError(
                "Tavily API key not provided. Please set TAVILY_API_KEY environment variable."
            )

        try:
            self._client = TavilyClient(api_key=api_key)
            logger.info("Tavily client initialized successfully")
        except Exception as exc:
            raise TavilyClientError(f"Failed to initialize Tavily client: {exc}") from exc

    def search(
        self,
        query: str,
        max_results: int = 5,
        search_depth: str = "basic",
        include_answer: bool = True,
        include_raw_content: bool = False,
    ) -> Dict:
        """
        执行搜索
        
        Args:
            query: 搜索查询字符串
            max_results: 最大返回结果数量（默认 5）
            search_depth: 搜索深度，"basic" 或 "advanced"（默认 "basic"）
            include_answer: 是否包含 AI 生成的答案（默认 True）
            include_raw_content: 是否包含原始内容（默认 False）
            
        Returns:
            Dict: 搜索结果，包含 results 和 answer 字段
        """
        if not query or not query.strip():
            raise ValueError("Search query cannot be empty")

        try:
            response = self._client.search(
                query=query.strip(),
                max_results=max_results,
                search_depth=search_depth,
                include_answer=include_answer,
                include_raw_content=include_raw_content,
            )
            logger.info(f"Tavily search completed for query: {query[:50]}...")
            return response
        except Exception as exc:
            logger.error(f"Tavily search failed: {exc}")
            raise TavilyClientError(f"Tavily search failed: {exc}") from exc

    def get_search_context(self, query: str, max_results: int = 5) -> str:
        """
        获取搜索结果的上下文字符串（用于 AI 聊天）
        
        Args:
            query: 搜索查询字符串
            max_results: 最大返回结果数量
            
        Returns:
            str: 格式化的搜索结果上下文
        """
        response = self.search(query=query, max_results=max_results, include_answer=True)
        
        context_parts = []
        
        # 添加 AI 生成的答案（如果有）
        if response.get("answer"):
            context_parts.append(f"答案: {response['answer']}")
        
        # 添加搜索结果
        results = response.get("results", [])
        if results:
            context_parts.append("\n搜索结果:")
            for i, result in enumerate(results, 1):
                title = result.get("title", "无标题")
                url = result.get("url", "")
                content = result.get("content", result.get("snippet", ""))
                context_parts.append(f"\n{i}. {title}")
                if url:
                    context_parts.append(f"   链接: {url}")
                if content:
                    context_parts.append(f"   内容: {content[:200]}...")
        
        return "\n".join(context_parts) if context_parts else "未找到相关结果"


@lru_cache(maxsize=1)
def get_tavily_client() -> TavilySearchClient:
    """提供单例 Tavily 客户端"""
    logger.info("Initializing Tavily client")
    return TavilySearchClient()


__all__ = ["TavilySearchClient", "TavilyClientError", "get_tavily_client"]

