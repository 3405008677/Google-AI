"""
Supervisor Architecture - API Routes

FastAPI 路由定义，提供：
1. SSE 流式聊天接口
2. 非流式聊天接口
3. 会话管理接口

使用依赖注入模式：
- 所有服务通过 Depends 注入
- 便于单元测试时替换 mock
- 清晰的依赖关系

SSE 流式传输说明：
- 实时推送思考过程（Thinking Process）
- 实时推送任务进度（Task Progress）
- 实时推送 Worker 输出（Worker Output）
- 避免用户在长时间等待中焦虑
"""

import uuid
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi import Response
from pydantic import BaseModel, Field

from src.router.agents.supervisor import UserContext
from src.core.dependencies import (
    get_supervisor_service_with_init_dep,
    get_worker_registry_dep,
    ensure_workers_registered_dep,
    get_user_context_dep,
)
from src.server.logging_setup import logger


# 创建路由器
router = APIRouter(prefix="/agents", tags=["Agents"])


# --- 请求/响应模型 ---


class ChatRequest(BaseModel):
    """聊天请求模型"""

    message: str = Field(..., description="用户消息", min_length=1, max_length=10000)
    thread_id: Optional[str] = Field(None, description="会话 ID，不提供则自动生成")

    # 用户上下文（可选）
    user_id: Optional[str] = Field(None, description="用户 ID")
    language: str = Field("zh-CN", description="语言偏好")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "先搜一下竞品价格，再查我们的库存，最后写个分析报告",
                "thread_id": "session-123",
                "user_id": "user-456",
                "language": "zh-CN",
            }
        }


class ChatResponse(BaseModel):
    """非流式聊天响应模型"""

    thread_id: str = Field(..., description="会话 ID")
    answer: str = Field(..., description="回答内容")
    cached: bool = Field(False, description="是否来自缓存")
    task_plan: Optional[list] = Field(None, description="任务计划")

    class Config:
        json_schema_extra = {
            "example": {
                "thread_id": "session-123",
                "answer": "这是 AI 的回答...",
                "cached": False,
                "task_plan": [
                    {"worker": "Researcher", "description": "搜索竞品价格", "status": "completed"},
                    {"worker": "DataAnalyst", "description": "分析库存数据", "status": "completed"},
                ],
            }
        }


# --- 内部辅助函数 ---


def _build_user_context(request: ChatRequest, base_context: UserContext) -> UserContext:
    """
    构建用户上下文

    合并请求参数和基础上下文。
    """
    return {
        **base_context,
        "user_id": request.user_id or base_context.get("user_id"),
        "session_id": request.thread_id or base_context.get("session_id"),
        "language": request.language,
    }


# --- API 路由 ---


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    http_request: Request,
    response: Response,
    service=Depends(get_supervisor_service_with_init_dep),
    base_context: UserContext = Depends(get_user_context_dep),
):
    """
    非流式聊天接口

    适用于简单查询或不需要实时反馈的场景。

    Args:
        request: 聊天请求
        http_request: HTTP 请求
        service: Supervisor 服务（依赖注入）
        base_context: 基础用户上下文（依赖注入）
    """
    # 会话连续性说明：
    # - LangGraph 的对话历史是以 thread_id 作为 key 保存/读取
    # - 若客户端每次都不传 thread_id，会被视为新会话，导致“看起来没有上下文”
    # 这里提供 cookie 回退机制：未显式传 thread_id 时，优先沿用 cookie 中的 thread_id。
    cookie_thread_id = http_request.cookies.get("thread_id")
    thread_id = request.thread_id or cookie_thread_id or f"thread-{uuid.uuid4().hex[:8]}"
    user_context = _build_user_context(request, base_context)

    # 把 thread_id 回写到 cookie，方便浏览器端自动续聊（非浏览器客户端仍建议显式传 thread_id）
    if not request.thread_id:
        response.set_cookie(
            key="thread_id",
            value=thread_id,
            httponly=True,
            samesite="lax",
        )

    try:
        result = await service.run(
            user_message=request.message,
            thread_id=thread_id,
            user_context=user_context,
        )

        # 处理响应
        if "error" in result:
            raise HTTPException(status_code=500, detail=result.get("error"))

        # 提取答案
        answer = result.get("answer", "")
        if not answer and "messages" in result:
            messages = result.get("messages", [])
            if messages:
                last_msg = messages[-1]
                answer = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)

        return ChatResponse(
            thread_id=thread_id,
            answer=answer,
            cached=result.get("cached", False),
            task_plan=result.get("task_plan"),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"聊天请求处理失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    http_request: Request,
    service=Depends(get_supervisor_service_with_init_dep),
    base_context: UserContext = Depends(get_user_context_dep),
):
    """
    SSE 流式聊天接口

    适用于复杂任务，实时推送：
    - 任务规划过程
    - 思考过程
    - Worker 执行进度
    - 最终结果

    响应格式：Server-Sent Events (SSE)
    每个事件格式：data: {"type": "...", "content": "...", ...}\n\n

    Args:
        request: 聊天请求
        http_request: HTTP 请求
        service: Supervisor 服务（依赖注入）
        base_context: 基础用户上下文（依赖注入）
    """
    cookie_thread_id = http_request.cookies.get("thread_id")
    thread_id = request.thread_id or cookie_thread_id or f"thread-{uuid.uuid4().hex[:8]}"
    user_context = _build_user_context(request, base_context)

    async def generate():
        """SSE 事件生成器"""
        try:
            async for event in service.run_stream(
                user_message=request.message,
                thread_id=thread_id,
                user_context=user_context,
                sse_format=True,  # 返回 SSE 格式字符串
            ):
                yield event
        except Exception as e:
            logger.error(f"流式聊天请求处理失败: {e}", exc_info=True)
            import json

            error_event = {
                "type": "error",
                "content": str(e),
            }
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"

    streaming_response = StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )

    # SSE 也回写 cookie，确保下一次请求能续用同一 thread_id
    if not request.thread_id:
        streaming_response.set_cookie(
            key="thread_id",
            value=thread_id,
            httponly=True,
            samesite="lax",
        )

    return streaming_response


@router.get("/chat/history/{thread_id}")
async def get_chat_history(
    thread_id: str,
    service=Depends(get_supervisor_service_with_init_dep),
):
    """
    获取会话历史

    Args:
        thread_id: 会话 ID
        service: Supervisor 服务（依赖注入）

    Returns:
        消息历史列表
    """
    try:
        history = await service.get_history(thread_id)

        if history is None:
            return JSONResponse(status_code=404, content={"detail": f"会话 {thread_id} 不存在或没有历史记录"})

        # 格式化历史消息
        formatted_history = []
        for msg in history:
            formatted_history.append(
                {
                    "type": msg.__class__.__name__,
                    "content": msg.content if hasattr(msg, 'content') else str(msg),
                    "name": getattr(msg, 'name', None),
                }
            )

        return {"thread_id": thread_id, "history": formatted_history}

    except Exception as e:
        logger.error(f"获取会话历史失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workers")
async def list_workers(
    _: None = Depends(ensure_workers_registered_dep),
    registry=Depends(get_worker_registry_dep),
):
    """
    列出所有可用的 Worker

    Args:
        registry: Worker 注册表（依赖注入）

    Returns:
        Worker 列表及其描述
    """
    return {
        "total": registry.count(),
        "workers": registry.get_stats()["workers"],
    }


@router.post("/workers/reset")
async def reset_workers(
    registry=Depends(get_worker_registry_dep),
):
    """
    重置所有 Worker 和服务实例

    用于开发调试或重新加载配置。

    Args:
        registry: Worker 注册表（依赖注入）
    """
    from src.router.agents.supervisor import (
        reset_service,
        reset_graph_app,
        register_all_workers,
    )

    # 清空 Worker 注册表
    registry.clear()

    # 重置服务和图
    reset_service()
    reset_graph_app()

    # 重新注册 Worker
    register_all_workers()

    return {"message": "Worker 和服务已重置", "workers_count": registry.count()}


# --- 注册路由到主应用 ---


def register_agent_routes(app, prefix: str = ""):
    """
    注册 Agent 路由到 FastAPI 应用

    Args:
        app: FastAPI 应用实例
        prefix: 路由前缀（如 "/api/v1"）

    使用方式：
        from src.router.agents.api import register_agent_routes
        register_agent_routes(app, prefix="/api/v1")

    注册后的端点：
        - POST {prefix}/agents/chat - 非流式聊天
        - POST {prefix}/agents/chat/stream - 流式聊天
        - GET {prefix}/agents/chat/history/{thread_id} - 会话历史
        - GET {prefix}/agents/workers - Worker 列表
        - POST {prefix}/agents/workers/reset - 重置 Worker
    """
    # 如果有前缀，需要创建带前缀的新路由器
    if prefix:
        from fastapi import APIRouter

        prefixed_router = APIRouter(prefix=prefix)
        prefixed_router.include_router(router)
        app.include_router(prefixed_router)
    else:
        app.include_router(router)

    logger.info(f"已注册 Agent API 路由，前缀: {prefix or '/'}")
