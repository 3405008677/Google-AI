"""
阿里云百炼 API 路由

前缀: /Bailian
接口：
- POST /Bailian/chat         同步返回完整回复
- POST /Bailian/chat/stream  SSE 流式返回回复
"""
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from ..common.models.chat_models import ChatRequest, ChatResponse, MessageRole
from ..common.utils.helpers import validate_request

from .services.chat_service import BailianChatService

logger = logging.getLogger(__name__)
ACCESS_LOGGER = None  # 将在模块加载时初始化专用日志器

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
    http_request: Request,
    request: ChatRequest,
    chat_service: BailianChatService = Depends(get_bailian_chat_service),
) -> ChatResponse:
    if error := validate_request(request.dict()):
        raise HTTPException(status_code=400, detail=error)

    log_request_metadata("chat", http_request, request)

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
    http_request: Request,
    request: ChatRequest,
    chat_service: BailianChatService = Depends(get_bailian_chat_service),
) -> StreamingResponse:
    if error := validate_request(request.dict()):
        raise HTTPException(status_code=400, detail=error)

    log_request_metadata("chat_stream", http_request, request)

    return StreamingResponse(
        chat_service.stream_response(request),
        media_type="text/event-stream",
    )


def initBailian(app, prefix=""):
    app.include_router(router, prefix=prefix)


__all__ = ["initBailian"]


def log_request_metadata(
    endpoint: str, http_request: Request, chat_request: ChatRequest
) -> None:
    """记录发起 AI 提问的基础信息"""
    client_ip = http_request.client.host if http_request.client else "unknown"
    relative_path = str(http_request.url.path)
    question = _extract_latest_question(chat_request).replace("\n", " ")
    log_message = (
        f"endpoint={endpoint} ip={client_ip} path={relative_path} question={question}"
    )
    logger.info(log_message)
    ACCESS_LOGGER.info(log_message)


def _extract_latest_question(chat_request: ChatRequest) -> str:
    if chat_request.text:
        return chat_request.text.strip()

    def _from_messages(messages):
        for msg in reversed(messages):
            role = msg.role if isinstance(msg.role, str) else msg.role.value
            if role == MessageRole.USER.value:
                return msg.content.strip()
        return ""

    if chat_request.messages:
        question = _from_messages(chat_request.messages)
        if question:
            return question

    if chat_request.history:
        question = _from_messages(chat_request.history)
        if question:
            return question

    return ""


def _init_access_logger() -> logging.Logger:
    """
    为百炼请求初始化专用日志文件 log/Bailian.log
    """
    log_dir = Path(__file__).resolve().parents[3] / "log"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "Bailian.log"
    access_logger = logging.getLogger("BailianAccess")

    if not any(
        isinstance(handler, logging.FileHandler)
        and Path(getattr(handler, "baseFilename", "")) == log_file
        for handler in access_logger.handlers
    ):
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(formatter)
        access_logger.addHandler(file_handler)
        access_logger.setLevel(logging.INFO)
        # 防止重复向根日志器传播，避免日志重复
        access_logger.propagate = False

    return access_logger


ACCESS_LOGGER = _init_access_logger()
