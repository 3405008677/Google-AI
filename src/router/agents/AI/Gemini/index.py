"""
Gemini AI 模型路由模块

此模块提供：
1. /chat - 非流式聊天接口
2. /chat/stream - SSE 流式聊天接口

前端传入对话内容，调用整体设计的 Supervisor Agents 架构。
使用 Google Gemini 模型。

环境变量配置：
- GEMINI_API_KEY: Gemini API 密钥
- GEMINI_MODEL: 模型名称（默认 gemini-2.5-flash）
"""

import uuid
import json
from typing import Optional
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from src.router.agents.supervisor import (
    get_service,
    register_all_workers,
    UserContext,
)
from src.config import get_gemini_model_config
from src.server.logging_setup import logger


# 创建路由器（prefix 在 initGemini 中设置）
router = APIRouter(tags=["Gemini AI"])


# --- 请求/响应模型 ---

class GeminiChatRequest(BaseModel):
    """Gemini 聊天请求模型"""
    message: str = Field(..., description="用户消息", min_length=1, max_length=10000)
    thread_id: Optional[str] = Field(None, description="会话 ID，不提供则自动生成")
    
    # 用户上下文（可选）
    user_id: Optional[str] = Field(None, description="用户 ID")
    language: str = Field("zh-CN", description="语言偏好")
    
    # 模型配置（可选，用于覆盖默认配置）
    model: Optional[str] = Field(None, description="模型名称，覆盖默认配置")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "帮我分析一下最近的市场趋势",
                "thread_id": "session-abc123",
                "user_id": "user-001",
                "language": "zh-CN",
                "model": "gemini-2.5-flash"
            }
        }


class GeminiChatResponse(BaseModel):
    """Gemini 聊天响应模型"""
    thread_id: str = Field(..., description="会话 ID")
    answer: str = Field(..., description="回答内容")
    cached: bool = Field(False, description="是否来自缓存")
    task_plan: Optional[list] = Field(None, description="任务计划")
    model: str = Field(..., description="使用的模型名称")
    
    class Config:
        json_schema_extra = {
            "example": {
                "thread_id": "session-abc123",
                "answer": "根据我的分析...",
                "cached": False,
                "task_plan": [],
                "model": "gemini-2.5-flash"
            }
        }


# --- 内部辅助函数 ---

def _ensure_workers_registered():
    """确保 Worker 已注册"""
    from src.router.agents.supervisor import get_registry
    registry = get_registry()
    if registry.is_empty():
        register_all_workers()
        logger.info("[Gemini] 已注册所有 Worker")


def _build_user_context(request: GeminiChatRequest, http_request: Request) -> UserContext:
    """构建用户上下文"""
    model_config = get_gemini_model_config()
    
    context: UserContext = {
        "user_id": request.user_id,
        "session_id": request.thread_id,
        "language": request.language,
        "timezone": "Asia/Shanghai",
        "permissions": [],
        "preferences": {},
    }
    
    # 注入 Gemini 模型配置
    context["preferences"]["gemini_model"] = {
        "model_name": request.model or model_config.model_name,
        "api_key": model_config.api_key,
    }
    
    # 从 HTTP 请求中提取更多上下文
    if hasattr(http_request.state, 'auth_token'):
        context["preferences"]["auth_token"] = http_request.state.auth_token
    
    return context


def _get_model_name(request: GeminiChatRequest) -> str:
    """获取使用的模型名称"""
    if request.model:
        return request.model
    model_config = get_gemini_model_config()
    return model_config.model_name


# --- API 路由 ---

@router.post("/chat", response_model=GeminiChatResponse)
async def gemini_chat(request: GeminiChatRequest, http_request: Request):
    """
    Gemini 非流式聊天接口
    
    使用 Google Gemini 模型处理请求。
    适用于简单查询或不需要实时反馈的场景。
    
    Args:
        request: 聊天请求，包含用户消息和可选的上下文信息
        http_request: HTTP 请求对象
        
    Returns:
        GeminiChatResponse: 包含回答内容和任务计划的响应
    """
    _ensure_workers_registered()
    
    # 检查配置
    model_config = get_gemini_model_config()
    if not model_config.is_configured():
        raise HTTPException(
            status_code=503, 
            detail="Gemini 模型未配置，请设置 GEMINI_API_KEY 环境变量"
        )
    
    thread_id = request.thread_id or f"gemini-{uuid.uuid4().hex[:8]}"
    user_context = _build_user_context(request, http_request)
    model_name = _get_model_name(request)
    
    try:
        service = get_service()
        result = await service.run(
            user_message=request.message,
            thread_id=thread_id,
            user_context=user_context,
        )
        
        # 处理错误响应
        if "error" in result:
            raise HTTPException(status_code=500, detail=result.get("error"))
        
        # 提取答案
        answer = result.get("answer", "")
        if not answer and "messages" in result:
            messages = result.get("messages", [])
            if messages:
                last_msg = messages[-1]
                answer = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
        
        return GeminiChatResponse(
            thread_id=thread_id,
            answer=answer,
            cached=result.get("cached", False),
            task_plan=result.get("task_plan"),
            model=model_name,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Gemini] 聊天请求处理失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def gemini_chat_stream(request: GeminiChatRequest, http_request: Request):
    """
    Gemini SSE 流式聊天接口
    
    使用 Google Gemini 模型处理请求并实时推送：
    - 任务规划过程
    - 思考过程
    - Worker 执行进度
    - 最终结果
    
    响应格式：Server-Sent Events (SSE)
    每个事件格式：data: {"type": "...", "content": "...", ...}\n\n
    
    Args:
        request: 聊天请求，包含用户消息和可选的上下文信息
        http_request: HTTP 请求对象
        
    Returns:
        StreamingResponse: SSE 流式响应
    """
    _ensure_workers_registered()
    
    # 检查配置
    model_config = get_gemini_model_config()
    if not model_config.is_configured():
        raise HTTPException(
            status_code=503, 
            detail="Gemini 模型未配置，请设置 GEMINI_API_KEY 环境变量"
        )
    
    thread_id = request.thread_id or f"gemini-{uuid.uuid4().hex[:8]}"
    user_context = _build_user_context(request, http_request)
    
    async def generate():
        """SSE 事件生成器"""
        try:
            service = get_service()
            async for event in service.run_stream(
                user_message=request.message,
                thread_id=thread_id,
                user_context=user_context,
                sse_format=True,
            ):
                yield event
        except Exception as e:
            logger.error(f"[Gemini] 流式聊天请求处理失败: {e}", exc_info=True)
            error_event = {
                "type": "error",
                "content": str(e),
            }
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/status")
async def gemini_status():
    """
    获取 Gemini AI 服务状态
    
    Returns:
        服务状态信息，包含模型配置和 Worker 信息
    """
    _ensure_workers_registered()
    
    from src.router.agents.supervisor import get_registry
    registry = get_registry()
    
    model_config = get_gemini_model_config()
    
    return {
        "status": "running" if model_config.is_configured() else "not_configured",
        "model": {
            "configured": model_config.is_configured(),
            "model_name": model_config.model_name,
            "api_key_set": bool(model_config.api_key),
        },
        "workers_count": registry.count(),
        "workers": registry.get_stats().get("workers", []),
    }


@router.get("/config")
async def get_model_config():
    """
    获取当前 Gemini 模型配置（不包含敏感信息）
    
    Returns:
        当前 Gemini 模型的配置信息
    """
    model_config = get_gemini_model_config()
    
    return {
        "configured": model_config.is_configured(),
        "model_name": model_config.model_name,
        "api_key_set": bool(model_config.api_key),
    }


@router.get("/models")
async def list_available_models():
    """
    列出可用的 Gemini 模型
    
    Returns:
        可用模型列表
    """
    return {
        "models": [
            {"name": "gemini-2.5-flash", "description": "Gemini 2.5 Flash，快速响应"},
            {"name": "gemini-2.5-pro", "description": "Gemini 2.5 Pro，更强能力"},
            {"name": "gemini-2.0-flash", "description": "Gemini 2.0 Flash，平衡版本"},
            {"name": "gemini-1.5-pro", "description": "Gemini 1.5 Pro，稳定版本"},
            {"name": "gemini-1.5-flash", "description": "Gemini 1.5 Flash，经济实惠"},
        ]
    }


# --- 路由注册函数 ---

def initGemini(app, prefix: str = "/Gemini"):
    """
    初始化 Gemini AI 路由
    
    将 Gemini AI 路由注册到 FastAPI 应用。
    
    环境变量配置：
        - GEMINI_API_KEY: Gemini API 密钥
        - GEMINI_MODEL: 模型名称（默认 gemini-2.5-flash）
    
    Args:
        app: FastAPI 应用实例
        prefix: 路由前缀，默认为 "/Gemini"
        
    使用方式：
        from src.router.agents.AI.Gemini.index import initGemini
        initGemini(app, prefix="/Gemini")
        
    注册后的端点：
        - POST {prefix}/chat - 非流式聊天
        - POST {prefix}/chat/stream - 流式聊天
        - GET {prefix}/status - 服务状态
        - GET {prefix}/config - 获取模型配置
        - GET {prefix}/models - 可用模型列表
    """
    model_config = get_gemini_model_config()
    if model_config.is_configured():
        logger.info(f"[Gemini] 已配置 Gemini 模型: {model_config.model_name}")
    else:
        logger.warning("[Gemini] 未配置 GEMINI_API_KEY，Gemini 服务将不可用")
    
    app.include_router(router, prefix=prefix)
    logger.info(f"[Gemini] 已注册 Gemini AI 路由，前缀: {prefix}")


# 导出公共接口
__all__ = [
    "initGemini",
    "GeminiChatRequest",
    "GeminiChatResponse",
    "router",
]

