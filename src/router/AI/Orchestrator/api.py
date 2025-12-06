"""
全能调度系统 API 路由

前缀: /Orchestrator
接口：
- POST /Orchestrator/chat         智能调度并返回响应
- POST /Orchestrator/chat/stream  SSE 流式返回响应

功能：
- 自动判断用户意图（聊天/搜索/数据库）
- 根据意图将任务分配给相应服务
- 统一返回格式
"""
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from ...common.models.chat_models import ChatRequest, ChatResponse
from ...common.utils.helpers import validate_request
from ...modules.logging_utils import init_access_logger, log_request_metadata
from .services.orchestrator_service import OrchestratorService

import logging

logger = logging.getLogger(__name__)

# 初始化访问日志器
access_logger = init_access_logger("Orchestrator", "Orchestrator.log")


class OrchestratorRouter:
    """全能调度系统路由类"""

    def __init__(self):
        self.service_name = "Orchestrator"
        self.router = None
        self._register_routes()

    def _register_routes(self):
        """注册路由端点"""
        from fastapi import APIRouter
        
        self.router = APIRouter(
            tags=["Orchestrator"],
            responses={404: {"description": "Not found"}}
        )

        @self.router.post(
            "/chat",
            response_model=ChatResponse,
            summary="智能调度聊天",
            description="自动判断用户意图，将任务分配给合适的服务（聊天/搜索/数据库）",
        )
        async def chat(
            http_request: Request,
            request: ChatRequest,
            orchestrator: OrchestratorService = Depends(lambda: OrchestratorService()),
        ) -> ChatResponse:
            if error := validate_request(request.dict()):
                raise HTTPException(status_code=400, detail=error)

            log_request_metadata(
                "chat",
                http_request,
                request,
                "Orchestrator",
                access_logger,
            )

            try:
                return await orchestrator.generate_response(request)
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.post(
            "/chat/stream",
            summary="智能调度聊天（流式）",
            description="使用 SSE 流式返回智能调度的响应",
        )
        async def chat_stream(
            http_request: Request,
            request: ChatRequest,
            orchestrator: OrchestratorService = Depends(lambda: OrchestratorService()),
        ) -> StreamingResponse:
            if error := validate_request(request.dict()):
                raise HTTPException(status_code=400, detail=error)

            log_request_metadata(
                "chat_stream",
                http_request,
                request,
                "Orchestrator",
                access_logger,
            )

            return StreamingResponse(
                orchestrator.stream_response(request),
                media_type="text/event-stream",
            )


# 创建路由实例
_orchestrator_router = OrchestratorRouter()


def initOrchestrator(app: FastAPI, prefix: str = ""):
    """初始化并注册全能调度系统路由"""
    app.include_router(_orchestrator_router.router, prefix=prefix)


__all__ = ["initOrchestrator"]

