"""
基础聊天服务类

提供所有 AI 聊天服务的通用功能，子类只需实现特定的客户端调用逻辑。

架构说明：
- BaseChatService: 抽象基类，定义通用流程
- MessagesBasedService: 处理消息数组的服务（OpenAI 兼容）
- PromptBasedService: 处理提示词字符串的服务（如 Gemini）
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Dict, Union

from fastapi import HTTPException

from ..common.models.chat_models import ChatRequest, ChatResponse, MessageRole
from .request_utils import generate_request_id, format_sse_event

logger = logging.getLogger(__name__)

"""
BaseChatService 类是所有聊天服务的基类，定义了通用的聊天服务流程：
1. 准备输入数据（_prepare_input）
2. 调用客户端生成响应（_generate_text / _stream_text）
3. 格式化并返回结果
"""


class BaseChatService(ABC):
    """
    基础聊天服务抽象类

    定义了通用的聊天服务流程：
    1. 准备输入数据（_prepare_input）
    2. 调用客户端生成响应（_generate_text / _stream_text）
    3. 格式化并返回结果
    """

    def __init__(self, service_name: str):
        """
        初始化基础聊天服务

        Args:
            service_name: 服务名称，用于日志记录
        """
        self.service_name = service_name

    async def generate_response(self, request: ChatRequest) -> ChatResponse:
        """
        生成聊天响应（同步）

        这是公共方法，子类不需要重写。它会调用子类实现的抽象方法。

        Args:
            request: 聊天请求对象

        Returns:
            ChatResponse: 包含AI响应的对象

        Raises:
            HTTPException: 当请求处理失败时抛出
        """
        request_id = generate_request_id()
        logger.info(f"Processing {self.service_name} chat request", extra={"request_id": request_id})

        try:
            # 子类实现具体的输入准备逻辑
            input_data = self._prepare_input(request)
            if not input_data:
                raise ValueError("Empty input data")

            start_time = time.perf_counter()
            # 子类实现具体的生成逻辑
            response_text = await self._call_client_generate(input_data)
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            return ChatResponse(
                request_id=request_id,
                text=response_text,
                latency_ms=latency_ms,
            )
        except Exception as e:
            logger.error(
                f"Failed to generate {self.service_name} response",
                exc_info=True,
                extra={"request_id": request_id},
            )
            raise HTTPException(status_code=500, detail=str(e))

    async def stream_response(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """
        流式生成聊天响应

        这是公共方法，子类不需要重写。它会调用子类实现的抽象方法。

        Args:
            request: 聊天请求对象

        Yields:
            str: SSE 格式的事件字符串
        """
        request_id = generate_request_id()
        logger.info(f"Starting {self.service_name} stream response", extra={"request_id": request_id})

        try:
            input_data = self._prepare_input(request)
            if not input_data:
                raise ValueError("Empty input data")

            # 子类实现具体的流式生成逻辑
            stream_result = await self._call_client_stream(input_data)

            # 检查是否是异步生成器
            import inspect

            if inspect.isasyncgen(stream_result):
                async for chunk in stream_result:
                    yield format_sse_event("message", chunk, request_id)
            else:
                # 同步生成器
                for chunk in stream_result:
                    yield format_sse_event("message", chunk, request_id)

            # 发送结束事件
            yield format_sse_event("end", "", request_id)
        except Exception as e:
            logger.error(
                f"{self.service_name} stream response failed",
                exc_info=True,
                extra={"request_id": request_id},
            )
            yield format_sse_event("error", str(e), request_id)

    @abstractmethod
    def _prepare_input(self, request: ChatRequest):
        """
        准备输入数据

        子类需要实现此方法，将 ChatRequest 转换为客户端需要的格式。

        Args:
            request: 聊天请求对象

        Returns:
            输入数据，类型由子类决定（List[Dict] 或 str）
        """
        pass

    @abstractmethod
    async def _call_client_generate(self, input_data) -> str:
        """
        调用客户端生成文本（同步）

        子类需要实现此方法，直接调用客户端的生成方法。

        Args:
            input_data: 由 _prepare_input 准备的数据

        Returns:
            str: 生成的文本
        """
        pass

    @abstractmethod
    async def _call_client_stream(self, input_data):
        """
        调用客户端流式生成文本

        子类需要实现此方法，直接调用客户端的流式生成方法。
        可以返回同步或异步生成器。

        Args:
            input_data: 由 _prepare_input 准备的数据

        Returns:
            AsyncGenerator[str, None] 或 Iterable[str]: 文本块生成器
        """
        pass


"""
MessagesBasedService 类是基于消息数组的聊天服务，适用于使用消息数组格式的客户端（如 Bailian、SelfHosted）。
子类只需要实现客户端调用方法。
"""


class MessagesBasedService(BaseChatService):
    """
    基于消息数组的聊天服务（OpenAI 兼容）

    适用于使用消息数组格式的客户端（如 Bailian、SelfHosted）。
    子类只需要实现客户端调用方法。
    """

    def _prepare_input(self, request: ChatRequest) -> List[Dict[str, str]]:
        """
        将 ChatRequest 转换为消息数组

        这是通用实现，子类通常不需要重写。

        Args:
            request: 聊天请求对象

        Returns:
            List[Dict[str, str]]: 消息数组
        """
        return self._compose_messages(request)

    def _compose_messages(self, request: ChatRequest) -> List[Dict[str, str]]:
        """
        将对话历史转换为 OpenAI 兼容的 messages 数组

        这是一个通用实现，子类可以直接使用或覆盖。

        Args:
            request: 聊天请求对象

        Returns:
            List[Dict[str, str]]: 消息列表
        """
        messages: List[Dict[str, str]] = []

        def _append(role: MessageRole | str, content: str) -> None:
            content = (content or "").strip()
            if not content:
                return
            role_value = role.value if isinstance(role, MessageRole) else role
            messages.append({"role": role_value, "content": content})

        # 如果提供了 messages 数组，直接使用
        if request.messages:
            for msg in request.messages:
                _append(msg.role, msg.content)
            if not messages:
                raise ValueError("Messages array cannot be empty.")
            return messages

        # 否则从 system_prompt、history、text 组合
        if request.system_prompt:
            _append("system", request.system_prompt)

        for msg in request.history:
            _append(msg.role, msg.content)

        _append("user", request.text or "")

        if not messages:
            raise ValueError("Unable to compose messages from request.")

        return messages


"""
PromptBasedService 类是基于提示词字符串的聊天服务，适用于使用字符串提示词的客户端（如 Gemini）。
子类只需要实现客户端调用方法和提示词组合逻辑。
"""


class PromptBasedService(BaseChatService):
    """
    基于提示词字符串的聊天服务

    适用于使用字符串提示词的客户端（如 Gemini）。
    子类只需要实现客户端调用方法和提示词组合逻辑。
    """

    def _prepare_input(self, request: ChatRequest) -> str:
        """
        将 ChatRequest 转换为提示词字符串

        子类需要实现 _compose_prompt 方法。

        Args:
            request: 聊天请求对象

        Returns:
            str: 提示词字符串
        """
        return self._compose_prompt(request)

    @abstractmethod
    def _compose_prompt(self, request: ChatRequest) -> str:
        """
        组合完整的提示词

        子类需要实现此方法，将 ChatRequest 转换为字符串提示词。

        Args:
            request: 聊天请求对象

        Returns:
            str: 提示词字符串
        """
        pass
