"""
阿里云百炼 API 路由

前缀: /Bailian
接口：
- POST /Bailian/chat         同步返回完整回复
- POST /Bailian/chat/stream  SSE 流式返回回复
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ..common.models.chat_models import ChatRequest, ChatResponse
from ..common.utils.helpers import validate_request

from .services.chat_service import BailianChatService

router = APIRouter(
    prefix="/Bailian",
    tags=["Bailian"],
    responses={404: {"description": "Not found"}},
)


def get_bailian_chat_service() -> BailianChatService:
    return BailianChatService()


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="同步生成百炼聊天响应",
    description="同步调用百炼 API 生成聊天响应",
)
async def bailian_chat(
    request: ChatRequest,
    chat_service: BailianChatService = Depends(get_bailian_chat_service),
) -> ChatResponse:
    if error := validate_request(request.dict()):
        raise HTTPException(status_code=400, detail=error)

    try:
        return await chat_service.generate_response(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/chat/stream",
    summary="流式生成百炼聊天响应",
    description="使用 SSE 流式返回百炼 API 的响应",
)
async def bailian_chat_stream(
    request: ChatRequest,
    chat_service: BailianChatService = Depends(get_bailian_chat_service),
) -> StreamingResponse:
    if error := validate_request(request.dict()):
        raise HTTPException(status_code=400, detail=error)

    return StreamingResponse(
        chat_service.stream_response(request),
        media_type="text/event-stream",
    )


def initBailian(app, prefix=""):
    app.include_router(router, prefix=prefix)


__all__ = ["initBailian"]
