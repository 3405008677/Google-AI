"""
基础 AI 聊天路由类

提供所有 AI 聊天路由的通用功能，子类只需实现特定的服务依赖注入。
"""
import logging
from typing import Type, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..common.models.chat_models import ChatRequest, ChatResponse
from ..common.utils.helpers import validate_request
from ..modules.base_chat_service import BaseChatService
from ..modules.logging_utils import init_access_logger, log_request_metadata

logger = logging.getLogger(__name__)


class BaseAIChatRouter:
    """
    基础 AI 聊天路由类
    
    提供标准的 /chat、/chat/stream 和可选的 /chat/terminate 端点。
    子类需要实现 get_chat_service 方法来提供具体的服务实例。
    """

    def __init__(
        self,
        service_name: str,
        service_class: Type[BaseChatService],
        enable_terminate: bool = True,
        enable_access_log: bool = False,
        log_filename: Optional[str] = None,
    ):
        """
        初始化基础路由
        
        Args:
            service_name: 服务名称（如 "Bailian", "GoogleAI", "SelfHosted"）
            service_class: 聊天服务类
            enable_terminate: 是否启用 /chat/terminate 端点
            enable_access_log: 是否启用访问日志
            log_filename: 访问日志文件名，如果不提供则使用 {service_name}.log
        """
        self.service_name = service_name
        self.service_class = service_class
        self.enable_terminate = enable_terminate
        self.enable_access_log = enable_access_log
        
        # 创建路由器
        self.router = APIRouter(
            tags=[service_name],
            responses={404: {"description": "Not found"}}
        )
        
        # 初始化访问日志器（如果需要）
        self.access_logger = None
        if enable_access_log:
            self.access_logger = init_access_logger(service_name, log_filename)
        
        # 注册路由
        self._register_routes()

    def _register_routes(self):
        """注册所有路由端点"""
        # 同步聊天端点
        @self.router.post(
            "/chat",
            response_model=ChatResponse,
            summary=f"同步生成{self.service_name}聊天响应",
            description=f"同步调用{self.service_name} API 生成聊天响应",
        )
        async def chat(
            http_request: Request,
            request: ChatRequest,
            chat_service: BaseChatService = Depends(self.get_chat_service),
        ) -> ChatResponse:
            if error := validate_request(request.dict()):
                raise HTTPException(status_code=400, detail=error)

            if self.enable_access_log:
                log_request_metadata(
                    "chat",
                    http_request,
                    request,
                    self.service_name,
                    self.access_logger,
                )
            else:
                logger.info(f"{self.service_name} chat request received")

            try:
                return await chat_service.generate_response(request)
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        # 流式聊天端点
        @self.router.post(
            "/chat/stream",
            summary=f"流式生成{self.service_name}聊天响应",
            description=f"使用 SSE 流式返回{self.service_name} API 的响应",
        )
        async def chat_stream(
            http_request: Request,
            request: ChatRequest,
            chat_service: BaseChatService = Depends(self.get_chat_service),
        ) -> StreamingResponse:
            if error := validate_request(request.dict()):
                raise HTTPException(status_code=400, detail=error)

            if self.enable_access_log:
                log_request_metadata(
                    "chat_stream",
                    http_request,
                    request,
                    self.service_name,
                    self.access_logger,
                )
            else:
                logger.info(f"{self.service_name} chat stream request received")

            return StreamingResponse(
                chat_service.stream_response(request),
                media_type="text/event-stream",
            )

        # 终止端点（可选）
        if self.enable_terminate:
            @self.router.post(
                "/chat/terminate",
                summary=f"终止{self.service_name}聊天会话",
                description=f"用于前端在需要时终止当前聊天会话（当前实现仅记录日志并返回状态）。",
            )
            async def chat_terminate(request: Request) -> dict:
                """
                终止当前聊天会话的占位路由。
                
                对于 SSE 流式请求，通常前端直接断开连接即可终止；该接口用于显式的"终止"语义，
                便于前端统一管理会话状态。
                """
                client_ip = request.client.host if request.client else "unknown"
                logger.info(f"{self.service_name} chat terminate requested from ip={client_ip}")
                return {"status": "terminated"}

    def get_chat_service(self) -> BaseChatService:
        """
        获取聊天服务实例
        
        子类需要实现此方法来提供具体的服务实例。
        
        Returns:
            BaseChatService: 聊天服务实例
        """
        raise NotImplementedError("Subclasses must implement get_chat_service")

    def init_router(self, app, prefix: str = ""):
        """
        初始化并注册路由到 FastAPI 应用
        
        Args:
            app: FastAPI 应用实例
            prefix: 路由前缀
        """
        app.include_router(self.router, prefix=prefix)

