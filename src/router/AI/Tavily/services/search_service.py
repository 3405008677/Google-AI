"""
Tavily 搜索服务模块

将 Tavily 搜索结果转换为聊天响应格式。
"""

import logging
import time
from typing import Dict

from fastapi import HTTPException

from ....common.models.chat_models import ChatRequest, ChatResponse
from ....modules.request_utils import generate_request_id
from ..models.tavily_client import get_tavily_client

logger = logging.getLogger(__name__)


class TavilySearchService:
    """
    Tavily 搜索服务类
    
    将搜索查询转换为格式化的搜索结果文本。
    """

    def __init__(self):
        self.service_name = "Tavily"
        self.client = get_tavily_client()

    async def generate_response(self, request: ChatRequest) -> ChatResponse:
        """
        生成搜索响应（同步）
        
        Args:
            request: 聊天请求对象，text 字段作为搜索查询
            
        Returns:
            ChatResponse: 包含搜索结果的响应对象
        """
        request_id = generate_request_id()
        logger.info(f"Processing Tavily search request", extra={"request_id": request_id})

        try:
            # 从请求中提取搜索查询
            query = self._extract_query(request)
            if not query:
                raise ValueError("Search query cannot be empty")

            start_time = time.perf_counter()
            
            # 执行搜索并获取格式化的上下文
            search_context = self.client.get_search_context(query, max_results=5)
            
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            return ChatResponse(
                request_id=request_id,
                text=search_context,
                latency_ms=latency_ms,
            )
        except Exception as e:
            logger.error(
                f"Failed to generate Tavily search response",
                exc_info=True,
                extra={"request_id": request_id},
            )
            raise HTTPException(status_code=500, detail=str(e))

    async def stream_response(self, request: ChatRequest):
        """
        流式返回搜索结果
        
        注意：Tavily 搜索是同步的，这里将结果分块返回以模拟流式。
        
        Args:
            request: 聊天请求对象
            
        Yields:
            str: SSE 格式的事件字符串
        """
        from ....modules.request_utils import format_sse_event
        
        request_id = generate_request_id()
        logger.info(f"Starting Tavily stream search", extra={"request_id": request_id})

        try:
            query = self._extract_query(request)
            if not query:
                raise ValueError("Search query cannot be empty")

            # 执行搜索
            search_context = self.client.get_search_context(query, max_results=5)
            
            # 将结果分块返回（每 100 个字符一块）
            chunk_size = 100
            for i in range(0, len(search_context), chunk_size):
                chunk = search_context[i:i + chunk_size]
                yield format_sse_event("message", chunk, request_id)
                # 添加小延迟以模拟流式效果
                import asyncio
                await asyncio.sleep(0.01)

            # 发送结束事件
            yield format_sse_event("end", "", request_id)
        except Exception as e:
            logger.error(
                f"Tavily stream search failed",
                exc_info=True,
                extra={"request_id": request_id},
            )
            yield format_sse_event("error", str(e), request_id)

    def _extract_query(self, request: ChatRequest) -> str:
        """
        从请求中提取搜索查询
        
        Args:
            request: 聊天请求对象
            
        Returns:
            str: 搜索查询字符串
        """
        # 优先使用 text 字段
        if request.text:
            return request.text.strip()
        
        # 如果没有 text，从 messages 中提取最后一条用户消息
        if request.messages:
            for msg in reversed(request.messages):
                if msg.role.value == "user":
                    return msg.content.strip()
        
        # 从 history 中提取最后一条用户消息
        if request.history:
            for msg in reversed(request.history):
                if msg.role.value == "user":
                    return msg.content.strip()
        
        return ""

