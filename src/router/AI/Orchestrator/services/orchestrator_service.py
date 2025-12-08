"""
全能调度服务

作为 SelfHosted 的智能调度层，根据用户意图：
- chat: 直接使用 SelfHosted 模型
- search: 先调用 Tavily 搜索，然后将搜索结果作为上下文给 SelfHosted 处理
- database: 先查询数据库，然后将结果给 SelfHosted 处理

所有结果最终都通过 SelfHosted 模型返回给用户。
"""
import logging
import time
from typing import AsyncGenerator
from copy import deepcopy

from fastapi import HTTPException

from ....common.models.chat_models import ChatRequest, ChatResponse, ChatMessage, MessageRole
from ....modules.request_utils import generate_request_id, format_sse_event
from ...SelfHosted.services.chat_service import SelfHostedChatService
from ...Tavily.models.tavily_client import get_tavily_client
from .intent_classifier import IntentClassifier, IntentType

logger = logging.getLogger(__name__)


class OrchestratorService:
    """
    全能调度服务
    
    作为 SelfHosted 的智能调度层，所有请求最终都通过 SelfHosted 模型返回。
    """

    def __init__(self):
        self.service_name = "Orchestrator"
        self.intent_classifier = IntentClassifier()
        self.chat_service = SelfHostedChatService()
        self._tavily_client = None  # 延迟初始化
        # TODO: 初始化数据库服务
        # self.database_service = DatabaseService()
    
    @property
    def tavily_client(self):
        """延迟初始化 Tavily 客户端"""
        if self._tavily_client is None:
            try:
                self._tavily_client = get_tavily_client()
            except Exception as e:
                logger.warning(f"Tavily client initialization failed: {e}. Search functionality will be unavailable.")
                self._tavily_client = False  # 标记为不可用
        return self._tavily_client if self._tavily_client is not False else None

    async def generate_response(self, request: ChatRequest) -> ChatResponse:
        """
        生成响应（同步）
        
        流程：
        1. 提取用户查询
        2. 判断意图
        3. 根据意图准备上下文：
           - chat: 直接使用原请求
           - search: 先搜索，将结果作为上下文
           - database: 先查数据库，将结果作为上下文
        4. 统一通过 SelfHosted 模型处理并返回
        
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

            # 创建请求副本，准备添加上下文
            enhanced_request = deepcopy(request)

            # 根据意图准备上下文
            if intent == IntentType.SEARCH.value:
                logger.info("Intent: SEARCH - Fetching search results first", extra={"request_id": request_id})
                
                # 检查 Tavily 客户端是否可用
                tavily = self.tavily_client
                if tavily is None:
                    # Tavily 不可用，告知用户
                    logger.warning("Tavily client not available, falling back to direct chat", extra={"request_id": request_id})
                    if not enhanced_request.system_prompt:
                        enhanced_request.system_prompt = "你是一个友好的AI助手，请用自然、友好的方式回答问题。"
                    enhanced_request.system_prompt += "\n\n注意：网络搜索功能当前不可用（Tavily API 未配置），我将基于已有知识回答。"
                else:
                    # 先搜索
                    search_context = tavily.get_search_context(user_query, max_results=5)
                    
                    # 将搜索结果作为系统提示或上下文
                    search_prompt = f"""用户的问题需要从网络搜索获取最新信息。我已经为你搜索了相关信息：

{search_context}

请根据以上搜索结果，回答用户的问题。如果搜索结果中没有相关信息，请如实告知用户。"""
                    
                    # 更新请求，将搜索结果作为上下文
                    if enhanced_request.system_prompt:
                        enhanced_request.system_prompt = f"{enhanced_request.system_prompt}\n\n{search_prompt}"
                    else:
                        enhanced_request.system_prompt = search_prompt
                
            elif intent == IntentType.DATABASE.value:
                logger.info("Intent: DATABASE - Querying database first", extra={"request_id": request_id})
                # TODO: 实现数据库查询
                db_result = "数据库查询功能正在开发中..."
                
                db_prompt = f"""用户的问题需要查询数据库。查询结果：

{db_result}

请根据以上查询结果，回答用户的问题。"""
                
                if enhanced_request.system_prompt:
                    enhanced_request.system_prompt = f"{enhanced_request.system_prompt}\n\n{db_prompt}"
                else:
                    enhanced_request.system_prompt = db_prompt
                    
            else:  # CHAT
                logger.info("Intent: CHAT - Direct chat", extra={"request_id": request_id})
                # 普通聊天，使用默认系统提示
                if not enhanced_request.system_prompt:
                    enhanced_request.system_prompt = "你是一个友好的AI助手，请用自然、友好的方式回答问题。"

            # 统一通过 SelfHosted 模型处理
            logger.info("Processing with SelfHosted model", extra={"request_id": request_id})
            response = await self.chat_service.generate_response(enhanced_request)

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
        
        流程同 generate_response，但以流式方式返回。
        
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

            # 创建请求副本
            enhanced_request = deepcopy(request)

            # 根据意图准备上下文
            if intent == IntentType.SEARCH.value:
                logger.info("Intent: SEARCH - Fetching search results first", extra={"request_id": request_id})
                
                # 检查 Tavily 客户端是否可用
                tavily = self.tavily_client
                if tavily is None:
                    # Tavily 不可用，告知用户
                    logger.warning("Tavily client not available, falling back to direct chat", extra={"request_id": request_id})
                    if not enhanced_request.system_prompt:
                        enhanced_request.system_prompt = "你是一个友好的AI助手，请用自然、友好的方式回答问题。"
                    enhanced_request.system_prompt += "\n\n注意：网络搜索功能当前不可用（Tavily API 未配置），我将基于已有知识回答。"
                else:
                    # 先搜索
                    search_context = tavily.get_search_context(user_query, max_results=5)
                    
                    # 将搜索结果作为上下文
                    search_prompt = f"""用户的问题需要从网络搜索获取最新信息。我已经为你搜索了相关信息：

{search_context}

请根据以上搜索结果，回答用户的问题。如果搜索结果中没有相关信息，请如实告知用户。"""
                    
                    if enhanced_request.system_prompt:
                        enhanced_request.system_prompt = f"{enhanced_request.system_prompt}\n\n{search_prompt}"
                    else:
                        enhanced_request.system_prompt = search_prompt
                    
            elif intent == IntentType.DATABASE.value:
                logger.info("Intent: DATABASE - Querying database first", extra={"request_id": request_id})
                # TODO: 实现数据库查询
                db_result = "数据库查询功能正在开发中..."
                
                db_prompt = f"""用户的问题需要查询数据库。查询结果：

{db_result}

请根据以上查询结果，回答用户的问题。"""
                
                if enhanced_request.system_prompt:
                    enhanced_request.system_prompt = f"{enhanced_request.system_prompt}\n\n{db_prompt}"
                else:
                    enhanced_request.system_prompt = db_prompt
                    
            else:  # CHAT
                logger.info("Intent: CHAT - Direct chat", extra={"request_id": request_id})
                if not enhanced_request.system_prompt:
                    enhanced_request.system_prompt = "你是一个友好的AI助手，请用自然、友好的方式回答问题。"

            # 统一通过 SelfHosted 模型流式处理
            logger.info("Streaming with SelfHosted model", extra={"request_id": request_id})
            async for chunk in self.chat_service.stream_response(enhanced_request):
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
