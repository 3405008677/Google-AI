"""
阿里云百炼聊天服务模块

接口风格与 googleAI.chat_service 一致，方便前端复用。
"""
import logging
import time
from typing import AsyncGenerator, List, Dict

from fastapi import HTTPException

from ...common.models.chat_models import ChatRequest, ChatResponse, MessageRole
from ..models.bailian_client import get_bailian_client

logger = logging.getLogger(__name__)


class BailianChatService:
    """百炼聊天服务类"""

    def __init__(self):
        self.client = get_bailian_client()

    async def generate_response(self, request: ChatRequest) -> ChatResponse:
        request_id = self._generate_request_id()
        logger.info("Processing Bailian chat request", extra={"request_id": request_id})

        try:
            messages = self._compose_messages(request)
            if not messages:
                raise ValueError("Empty messages")

            start_time = time.perf_counter()
            # 调用百炼客户端
            response_text = self.client.generate_text(messages)
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            return ChatResponse(
                request_id=request_id,
                text=response_text,
                latency_ms=latency_ms,
            )
        except Exception as e:
            logger.error(
                "Failed to generate Bailian response",
                exc_info=True,
                extra={"request_id": request_id},
            )
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
        logger.info("Starting Bailian stream response", extra={"request_id": request_id})

        try:
            messages = self._compose_messages(request)
            if not messages:
                raise ValueError("Empty messages")

            # 流式调用百炼客户端（stream_text 返回同步生成器，这里使用普通 for）
            for chunk in self.client.stream_text(messages):
                yield self._format_sse_event("message", chunk, request_id)

            # 发送结束事件
            yield self._format_sse_event("end", "", request_id)
        except Exception as e:
            logger.error(
                "Bailian stream response failed",
                exc_info=True,
                extra={"request_id": request_id},
            )
            yield self._format_sse_event("error", str(e), request_id)

    def _compose_messages(self, request: ChatRequest) -> List[Dict[str, str]]:
        """将对话历史转换为 OpenAI 兼容的 messages 数组，实现多轮对话。"""
        messages: List[Dict[str, str]] = []

        def _append(role: MessageRole | str, content: str) -> None:
            content = (content or "").strip()
            if not content:
                return
            role_value = role.value if isinstance(role, MessageRole) else role
            messages.append({"role": role_value, "content": content})

        if request.messages:
            for msg in request.messages:
                _append(msg.role, msg.content)
            if not messages:
                raise ValueError("Messages array cannot be empty.")
            return messages

        if request.system_prompt:
            _append("system", request.system_prompt)

        for msg in request.history:
            _append(msg.role, msg.content)

        _append("user", request.text or "")

        if not messages:
            raise ValueError("Unable to compose messages from request.")

        return messages

    @staticmethod
    def _generate_request_id() -> str:
        import uuid

        return uuid.uuid4().hex

    @staticmethod
    def _format_sse_event(event_type: str, data: str, request_id: str) -> str:
        return f"id: {request_id}\nevent: {event_type}\ndata: {data}\n\n"
