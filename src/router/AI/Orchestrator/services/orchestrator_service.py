"""
全能调度服务

根据用户意图，将任务分配给不同的服务：
- chat: SelfHosted 模型（普通聊天）
- search: Tavily 搜索（网络搜索）
- database: 数据库查询（待实现）
"""
import logging
import time
from typing import AsyncGenerator

from fastapi import HTTPException

from ....common.models.chat_models import ChatRequest, ChatResponse
from ....modules.request_utils import generate_request_id, format_sse_event
from ...SelfHosted.services.chat_service import SelfHostedChatService
from ...Tavily.services.search_service import TavilySearchService
from .intent_classifier import IntentClassifier, IntentType

logger = logging.getLogger(__name__)


class OrchestratorService:
    """
    全能调度服务
    
    智能判断用户意图，并将任务分配给合适的服务。
    """

    def __init__(self):
        self.service_name = "Orchestrator"
        self.intent_classifier = IntentClassifier()
        self.chat_service = SelfHostedChatService()
        self.search_service = TavilySearchService()
        # TODO: 初始化数据库服务
        # self.database_service = DatabaseService()

    async def generate_response(self, request: ChatRequest) -> ChatResponse:
        """
        生成响应（同步）
        
        流程：
        1. 提取用户查询
        2. 判断意图
        3. 根据意图调用相应服务
        4. 返回结果
        
        Args:
            request: 聊天请求对象
            
        Returns:
            ChatResponse: 响应对象
        """
        request_id = generate_request_id()
        logger.info(f"Processing orchestrator request", extra={"request_id": request_id})

        try:
            # 提取用户查询
            user_query = self._extract_query(request)
            if not user_query:
                raise ValueError("User query cannot be empty")

            start_time = time.perf_counter()

            # 判断意图
            intent_result = await self.intent_classifier.classify(user_query)
            intent = intent_result["intent"]
            confidence = intent_result["confidence"]
            reason = intent_result.get("reason", "")

            logger.info(
                f"Intent: {intent} (confidence: {confidence}, reason: {reason})",
                extra={"request_id": request_id}
            )

            # 根据意图调用相应服务
            if intent == IntentType.SEARCH.value:
                logger.info("Routing to Tavily search service", extra={"request_id": request_id})
                response = await self.search_service.generate_response(request)
                # 在响应中添加意图信息
                response.text = f"[意图: 网络搜索 | 置信度: {confidence:.2f}]\n\n{response.text}"
                
            elif intent == IntentType.DATABASE.value:
                logger.info("Routing to database service", extra={"request_id": request_id})
                # TODO: 实现数据库查询服务
                response = ChatResponse(
                    request_id=request_id,
                    text=f"[意图: 数据库查询 | 置信度: {confidence:.2f}]\n\n数据库查询功能正在开发中...",
                    latency_ms=0,
                )
                
            else:  # CHAT
                logger.info("Routing to SelfHosted chat service", extra={"request_id": request_id})
                # 为聊天服务添加上下文，说明这是普通对话
                # 创建请求副本，避免修改原始请求
                from copy import deepcopy
                chat_request = deepcopy(request)
                if not chat_request.system_prompt:
                    chat_request.system_prompt = "你是一个友好的AI助手，请用自然、友好的方式回答问题。"
                
                response = await self.chat_service.generate_response(chat_request)

            latency_ms = int((time.perf_counter() - start_time) * 1000)
            response.latency_ms = latency_ms

            return response

        except Exception as e:
            logger.error(
                f"Orchestrator request failed",
                exc_info=True,
                extra={"request_id": request_id},
            )
            raise HTTPException(status_code=500, detail=str(e))

    async def stream_response(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """
        流式生成响应
        
        Args:
            request: 聊天请求对象
            
        Yields:
            str: SSE 格式的事件字符串
        """
        request_id = generate_request_id()
        logger.info(f"Starting orchestrator stream response", extra={"request_id": request_id})

        try:
            # 提取用户查询
            user_query = self._extract_query(request)
            if not user_query:
                raise ValueError("User query cannot be empty")

            # 判断意图
            intent_result = await self.intent_classifier.classify(user_query)
            intent = intent_result["intent"]
            confidence = intent_result["confidence"]

            logger.info(
                f"Intent: {intent} (confidence: {confidence})",
                extra={"request_id": request_id}
            )

            # 发送意图信息
            intent_info = f"[意图: {intent} | 置信度: {confidence:.2f}]\n\n"
            yield format_sse_event("message", intent_info, request_id)

            # 根据意图调用相应服务
            if intent == IntentType.SEARCH.value:
                logger.info("Streaming from Tavily search service", extra={"request_id": request_id})
                async for chunk in self.search_service.stream_response(request):
                    yield chunk
                    
            elif intent == IntentType.DATABASE.value:
                logger.info("Streaming from database service", extra={"request_id": request_id})
                # TODO: 实现数据库查询流式返回
                yield format_sse_event("message", "数据库查询功能正在开发中...", request_id)
                yield format_sse_event("end", "", request_id)
                
            else:  # CHAT
                logger.info("Streaming from SelfHosted chat service", extra={"request_id": request_id})
                # 为聊天服务添加上下文
                from copy import deepcopy
                chat_request = deepcopy(request)
                if not chat_request.system_prompt:
                    chat_request.system_prompt = "你是一个友好的AI助手，请用自然、友好的方式回答问题。"
                
                async for chunk in self.chat_service.stream_response(chat_request):
                    yield chunk

        except Exception as e:
            logger.error(
                f"Orchestrator stream response failed",
                exc_info=True,
                extra={"request_id": request_id},
            )
            yield format_sse_event("error", str(e), request_id)

    def _extract_query(self, request: ChatRequest) -> str:
        """
        从请求中提取用户查询
        
        Args:
            request: 聊天请求对象
            
        Returns:
            str: 用户查询字符串
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

