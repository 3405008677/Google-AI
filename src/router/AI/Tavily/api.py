"""
Tavily 搜索 API 路由

前缀: /Tavily
接口：
- POST /Tavily/search         同步返回搜索结果
- POST /Tavily/search/stream  SSE 流式返回搜索结果
"""
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from ...common.models.chat_models import ChatRequest, ChatResponse
from ...common.utils.helpers import validate_request
from ...modules.logging_utils import init_access_logger, log_request_metadata
from .services.search_service import TavilySearchService

import logging

logger = logging.getLogger(__name__)

# 初始化访问日志器
access_logger = init_access_logger("Tavily", "Tavily.log")


class TavilyRouter:
    """Tavily 搜索路由类"""

    def __init__(self):
        self.service_name = "Tavily"
        self.router = None
        self._register_routes()

    def _register_routes(self):
        """注册路由端点"""
        from fastapi import APIRouter
        
        self.router = APIRouter(
            tags=["Tavily"],
            responses={404: {"description": "Not found"}}
        )

        @self.router.post(
            "/search",
            response_model=ChatResponse,
            summary="同步执行 Tavily 搜索",
            description="同步调用 Tavily API 执行搜索并返回结果",
        )
        async def search(
            http_request: Request,
            request: ChatRequest,
            search_service: TavilySearchService = Depends(lambda: TavilySearchService()),
        ) -> ChatResponse:
            if error := validate_request(request.dict()):
                raise HTTPException(status_code=400, detail=error)

            log_request_metadata(
                "search",
                http_request,
                request,
                "Tavily",
                access_logger,
            )

            try:
                return await search_service.generate_response(request)
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.post(
            "/search/stream",
            summary="流式执行 Tavily 搜索",
            description="使用 SSE 流式返回 Tavily 搜索结果",
        )
        async def search_stream(
            http_request: Request,
            request: ChatRequest,
            search_service: TavilySearchService = Depends(lambda: TavilySearchService()),
        ) -> StreamingResponse:
            if error := validate_request(request.dict()):
                raise HTTPException(status_code=400, detail=error)

            log_request_metadata(
                "search_stream",
                http_request,
                request,
                "Tavily",
                access_logger,
            )

            return StreamingResponse(
                search_service.stream_response(request),
                media_type="text/event-stream",
            )


# 创建路由实例
_tavily_router = TavilyRouter()


def initTavily(app: FastAPI, prefix: str = ""):
    """初始化并注册 Tavily 路由"""
    app.include_router(_tavily_router.router, prefix=prefix)


__all__ = ["initTavily"]

