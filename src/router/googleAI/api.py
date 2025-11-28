"""
Google AI API 路由

定义与 Google Gemini AI 交互的 API 端点。
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ..common.models.chat_models import ChatRequest, ChatResponse
from ..common.utils.helpers import validate_request
from .services.chat_service import ChatService
from .models.gemini_client import get_gemini_client

# 创建 API 路由器
router = APIRouter(
    prefix="/GoogleAI",
    tags=["Google AI"],
    responses={404: {"description": "Not found"}},
)


def get_chat_service() -> ChatService:
    return ChatService(get_gemini_client())


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="同步生成聊天响应",
    description="同步调用 Gemini API 生成聊天响应",
)
async def chat(
    request: ChatRequest, chat_service: ChatService = Depends(get_chat_service)
) -> ChatResponse:
    # 验证请求
    if error := validate_request(request.dict()):
        raise HTTPException(status_code=400, detail=error)

    try:
        return await chat_service.generate_response(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/chat/stream",
    summary="流式生成聊天响应",
    description="使用 Server-Sent Events (SSE) 流式返回 Gemini 的响应",
)
async def chat_stream(
    request: ChatRequest, chat_service: ChatService = Depends(get_chat_service)
) -> StreamingResponse:
    # 验证请求
    if error := validate_request(request.dict()):
        raise HTTPException(status_code=400, detail=error)

    return StreamingResponse(
        chat_service.stream_response(request), media_type="text/event-stream"
    )


def initGoogleAI(app, prefix=""):
    # include_router 会将 router 中定义的所有端点添加到 app 中
    app.include_router(router, prefix=prefix)


__all__ = ["initGoogleAI"]
