"""
自定义 AI 模型路由模块

此模块提供：
1. /chat - 非流式聊天接口
2. /chat/stream - SSE 流式聊天接口

前端传入对话内容，调用整体设计的 Supervisor Agents 架构。
支持通过环境变量配置自定义模型：
- SELF_MODEL_BASE_URL: 自建模型 API 地址
- SELF_MODEL_NAME: 模型名称
- SELF_MODEL_API_KEY: API 密钥
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
from src.config import get_customize_model_config
from src.server.logging_setup import logger


# 创建路由器（prefix 在 initCustomize 中设置）
router = APIRouter(tags=["Customize AI"])


# --- 请求/响应模型 ---

class CustomizeChatRequest(BaseModel):
    """自定义聊天请求模型"""
    message: str = Field(..., description="用户消息", min_length=1, max_length=10000)
    thread_id: Optional[str] = Field(None, description="会话 ID，不提供则自动生成")
    
    # 用户上下文（可选）
    user_id: Optional[str] = Field(None, description="用户 ID")
    language: str = Field("zh-CN", description="语言偏好")
    
    # 自定义配置（可选）
    model_config_extra: Optional[dict] = Field(None, description="额外的模型配置")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "帮我分析一下最近的市场趋势",
                "thread_id": "session-abc123",
                "user_id": "user-001",
                "language": "zh-CN",
                "model_config_extra": {}
            }
        }


class CustomizeChatResponse(BaseModel):
    """自定义聊天响应模型"""
    thread_id: str = Field(..., description="会话 ID")
    answer: str = Field(..., description="回答内容")
    cached: bool = Field(False, description="是否来自缓存")
    task_plan: Optional[list] = Field(None, description="任务计划")
    
    class Config:
        json_schema_extra = {
            "example": {
                "thread_id": "session-abc123",
                "answer": "根据我的分析...",
                "cached": False,
                "task_plan": []
            }
        }


# --- 内部辅助函数 ---

def _ensure_workers_registered():
    """确保 Worker 已注册"""
    from src.router.agents.supervisor import get_registry
    registry = get_registry()
    if registry.is_empty():
        register_all_workers()
        logger.info("[Customize] 已注册所有 Worker")


def _build_user_context(request: CustomizeChatRequest, http_request: Request) -> UserContext:
    """构建用户上下文"""
    context: UserContext = {
        "user_id": request.user_id,
        "session_id": request.thread_id,
        "language": request.language,
        "timezone": "Asia/Shanghai",
        "permissions": [],
        "preferences": {},
    }
    
    # 注入自定义模型配置
    model_config = get_customize_model_config()
    if model_config.is_configured():
        context["preferences"]["custom_model"] = {
            "base_url": model_config.base_url,
            "model_name": model_config.model_name,
            "api_key": model_config.api_key,
        }
    
    # 添加额外的模型配置（请求级别覆盖）
    if request.model_config_extra:
        context["preferences"]["model_config"] = request.model_config_extra
    
    # 从 HTTP 请求中提取更多上下文
    if hasattr(http_request.state, 'auth_token'):
        context["preferences"]["auth_token"] = http_request.state.auth_token
    
    return context


# --- API 路由 ---

@router.post("/chat", response_model=CustomizeChatResponse)
async def customize_chat(request: CustomizeChatRequest, http_request: Request):
    """
    非流式聊天接口
    
    前端传入对话内容，调用 Supervisor Agents 处理请求。
    适用于简单查询或不需要实时反馈的场景。
    
    Args:
        request: 聊天请求，包含用户消息和可选的上下文信息
        http_request: HTTP 请求对象
        
    Returns:
        ChatResponse: 包含回答内容和任务计划的响应
    """
    _ensure_workers_registered()
    
    thread_id = request.thread_id or f"customize-{uuid.uuid4().hex[:8]}"
    user_context = _build_user_context(request, http_request)
    
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
        
        return CustomizeChatResponse(
            thread_id=thread_id,
            answer=answer,
            cached=result.get("cached", False),
            task_plan=result.get("task_plan"),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Customize] 聊天请求处理失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def customize_chat_stream(request: CustomizeChatRequest, http_request: Request):
    """
    SSE 流式聊天接口
    
    前端传入对话内容，调用 Supervisor Agents 并实时推送：
    - 任务规划过程
    - 思考过程
    - Worker 执行进度
    - 最终结果
    
    响应格式：Server-Sent Events (SSE)
    每个事件格式：data: {"type": "...", "content": "...", ...}\n\n
    
    事件类型说明：
    - thinking: 思考过程
    - task_plan: 任务规划
    - worker_start: Worker 开始执行
    - worker_progress: Worker 执行进度
    - worker_complete: Worker 执行完成
    - answer: 最终答案
    - error: 错误信息
    - done: 完成标志
    
    Args:
        request: 聊天请求，包含用户消息和可选的上下文信息
        http_request: HTTP 请求对象
        
    Returns:
        StreamingResponse: SSE 流式响应
    """
    _ensure_workers_registered()
    
    thread_id = request.thread_id or f"customize-{uuid.uuid4().hex[:8]}"
    user_context = _build_user_context(request, http_request)
    
    async def generate():
        """SSE 事件生成器"""
        try:
            service = get_service()
            async for event in service.run_stream(
                user_message=request.message,
                thread_id=thread_id,
                user_context=user_context,
                sse_format=True,  # 返回 SSE 格式字符串
            ):
                yield event
        except Exception as e:
            logger.error(f"[Customize] 流式聊天请求处理失败: {e}", exc_info=True)
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
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        }
    )


@router.get("/status")
async def customize_status():
    """
    获取自定义 AI 服务状态
    
    Returns:
        服务状态信息，包含模型配置和 Worker 信息
    """
    _ensure_workers_registered()
    
    from src.router.agents.supervisor import get_registry
    registry = get_registry()
    
    # 获取自定义模型配置
    model_config = get_customize_model_config()
    
    return {
        "status": "running",
        "model": {
            "configured": model_config.is_configured(),
            "base_url": model_config.base_url,
            "model_name": model_config.model_name,
            # 不暴露 API Key，只显示是否已配置
            "api_key_set": bool(model_config.api_key),
        },
        "workers_count": registry.count(),
        "workers": registry.get_stats().get("workers", []),
    }


@router.get("/config")
async def get_model_config():
    """
    获取当前模型配置（不包含敏感信息）
    
    Returns:
        当前自定义模型的配置信息
    """
    model_config = get_customize_model_config()
    
    return {
        "configured": model_config.is_configured(),
        "base_url": model_config.base_url,
        "model_name": model_config.model_name,
        "api_key_set": bool(model_config.api_key),
    }


# --- 路由注册函数 ---

def initCustomize(app, prefix: str = "/Customize"):
    """
    初始化自定义 AI 路由
    
    将自定义 AI 路由注册到 FastAPI 应用。
    支持通过环境变量配置自定义模型位置。
    
    环境变量配置：
        - SELF_MODEL_BASE_URL: 自建模型 API 地址（如 https://ai.example.com/v1）
        - SELF_MODEL_NAME: 模型名称
        - SELF_MODEL_API_KEY: API 密钥
    
    Args:
        app: FastAPI 应用实例
        prefix: 路由前缀，默认为 "/Customize"
        
    使用方式：
        from src.router.agents.AI.Customize.index import initCustomize
        initCustomize(app, prefix="/Customize")
        
    注册后的端点：
        - POST {prefix}/chat - 非流式聊天
        - POST {prefix}/chat/stream - 流式聊天
        - GET {prefix}/status - 服务状态（含模型配置）
        - GET {prefix}/config - 获取模型配置
    """
    # 检查并记录模型配置状态
    model_config = get_customize_model_config()
    if model_config.is_configured():
        logger.info(f"[Customize] 已配置自定义模型: {model_config.model_name} @ {model_config.base_url}")
    else:
        logger.warning("[Customize] 未配置自定义模型，将使用默认配置")
    
    app.include_router(router, prefix=prefix)
    logger.info(f"[Customize] 已注册自定义 AI 路由，前缀: {prefix}")


# 导出公共接口
__all__ = [
    "initCustomize",
    "CustomizeChatRequest",
    "CustomizeChatResponse",
    "router",
]

