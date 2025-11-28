"""
聊天服务模块

处理与聊天相关的业务逻辑，包括：
- 组合提示词
- 调用 Gemini API
- 错误处理
"""
import logging
import time
from typing import AsyncGenerator, Optional

from fastapi import HTTPException

from ..models.chat_models import ChatRequest, ChatResponse, MessageRole

logger = logging.getLogger(__name__)

class ChatService:
    """聊天服务类，封装聊天相关业务逻辑"""
    
    def __init__(self, gemini_client):
        """
        初始化聊天服务
        
        Args:
            gemini_client: Gemini API 客户端实例
        """
        self.gemini_client = gemini_client
    
    async def generate_response(self, request: ChatRequest) -> ChatResponse:
        """
        生成聊天响应（同步）
        
        Args:
            request: 聊天请求对象
            
        Returns:
            ChatResponse: 包含AI响应的对象
            
        Raises:
            HTTPException: 当请求处理失败时抛出
        """
        request_id = self._generate_request_id()
        logger.info("Processing chat request", extra={"request_id": request_id})
        
        try:
            prompt = self._compose_prompt(request)
            if not prompt.strip():
                raise ValueError("Empty prompt")
                
            start_time = time.perf_counter()
            
            # 调用 Gemini API 生成响应
            response_text = await self.gemini_client.generate_text(prompt)
            
            # 计算处理耗时
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            
            return ChatResponse(
                request_id=request_id,
                text=response_text,
                latency_ms=latency_ms
            )
            
        except Exception as e:
            logger.error("Failed to generate response", 
                        exc_info=True, 
                        extra={"request_id": request_id})
            raise HTTPException(status_code=500, detail=str(e))
    
    async def stream_response(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """
        流式生成聊天响应
        
        Args:
            request: 聊天请求对象
            
        Yields:
            str: SSE 格式的事件字符串
        """
        request_id = self._generate_request_id()
        logger.info("Starting stream response", extra={"request_id": request_id})
        
        try:
            prompt = self._compose_prompt(request)
            if not prompt.strip():
                raise ValueError("Empty prompt")
                
            # 流式调用 Gemini API
            async for chunk in self.gemini_client.stream_text(prompt):
                yield self._format_sse_event("message", chunk, request_id)
                
            # 发送结束事件
            yield self._format_sse_event("end", "", request_id)
            
        except Exception as e:
            logger.error("Stream response failed", 
                        exc_info=True, 
                        extra={"request_id": request_id})
            yield self._format_sse_event("error", str(e), request_id)
    
    def _compose_prompt(self, request: ChatRequest) -> str:
        """组合完整的提示词"""
        segments = []
        
        # 添加系统提示（如果存在）
        if request.system_prompt:
            segments.append(f"[System]\n{request.system_prompt.strip()}")
        
        # 添加历史消息
        for msg in request.history:
            role = msg.role.value.capitalize()
            segments.append(f"[{role}]\n{msg.content.strip()}")
        
        # 添加当前用户输入
        segments.append(f"[User]\n{request.text.strip()}")
        
        return "\n\n".join(segments)
    
    @staticmethod
    def _generate_request_id() -> str:
        """生成唯一的请求ID"""
        import uuid
        return uuid.uuid4().hex
    
    @staticmethod
    def _format_sse_event(event_type: str, data: str, request_id: str) -> str:
        """
        格式化SSE事件
        
        Args:
            event_type: 事件类型（message/error/end）
            data: 事件数据
            request_id: 请求ID
            
        Returns:
            str: 格式化后的SSE事件字符串
        """
        return f"id: {request_id}\nevent: {event_type}\ndata: {data}\n\n"
