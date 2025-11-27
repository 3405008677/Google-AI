"""
Google AI (Gemini) 路由模块

此模块提供与 Google Gemini AI 模型交互的 API 端点：
1. 同步内容生成端点 (/content) - 等待完整响应后返回
2. 流式内容生成端点 (/stream) - 使用 SSE 实时推送生成内容

主要功能：
- 处理用户的文本输入和对话历史
- 调用 Gemini API 生成 AI 响应
- 提供错误处理和日志记录
- 支持系统提示和对话上下文管理
"""

import logging  # 导入 logging 模块，用于记录应用程序运行时的日志信息
import time  # 导入 time 模块，用于计算 API 响应时间和性能指标
import uuid  # 导入 uuid 模块，用于生成唯一的请求 ID，便于追踪和调试
from enum import Enum  # 导入 Enum 枚举类型，用于定义消息角色的固定选项
from typing import List  # 导入 List 类型提示，用于类型注解和静态类型检查

import anyio  # 导入 anyio 库，用于在异步环境中执行同步任务，避免阻塞事件循环
from fastapi import APIRouter, Depends, HTTPException  # 导入 FastAPI 核心对象
# - APIRouter: 用于创建路由器和定义端点
# - Depends: 用于依赖注入，自动管理 Gemini 客户端的创建和生命周期
# - HTTPException: 用于抛出 HTTP 错误响应
from fastapi.responses import StreamingResponse  # 导入 StreamingResponse，用于发送服务器发送事件 (SSE) 流式响应
from pydantic import BaseModel, Field  # 导入 Pydantic 基类和字段验证
# - BaseModel: 用于定义数据模型和自动验证请求/响应数据
# - Field: 用于定义字段的验证规则和文档说明
from starlette.concurrency import iterate_in_threadpool  # 导入线程池异步迭代器，用于在线程池中异步迭代同步生成器

from src.modules.gemini_client import GeminiClient, GeminiClientError, get_gemini_client
# - GeminiClient: Gemini API 客户端封装类
# - GeminiClientError: 自定义的 Gemini 客户端错误异常类
# - get_gemini_client: 依赖注入函数，提供单例 Gemini 客户端实例

logger = logging.getLogger(__name__)  # 创建模块级日志记录器，用于记录此模块的运行日志

# 创建 Google AI 子路由器
# 此路由器将包含所有与 Gemini AI 相关的 API 端点
router = APIRouter(
    prefix="/GoogleAI",  # 统一前缀，所有此路由器的端点都会自动添加此前缀
    # 例如：/content 会变成 /GoogleAI/content
    tags=["Google AI"],  # API 文档标签，用于在 Swagger UI 中分组显示相关端点
    responses={404: {"description": "Not found"}},  # 默认 404 响应描述，用于 API 文档生成
)


class MessageRole(str, Enum):
    """
    消息角色枚举类
    
    定义对话中消息的类型，用于区分不同角色的消息：
    - user: 用户发送的消息
    - assistant: AI 助手（Gemini）生成的回复
    - system: 系统提示，用于设定 AI 的行为和角色
    
    继承自 str 和 Enum，使其既可以作为字符串使用，又具有枚举的类型安全性。
    """
    user = "user"  # 用户消息，表示来自用户的输入
    assistant = "assistant"  # 助手消息，表示来自 AI 助手的回复
    system = "system"  # 系统提示，用于设定 AI 的行为模式、角色或指令


class ChatMessage(BaseModel):
    """
    单条历史消息数据模型
    
    用于表示对话历史中的一条消息，包含消息的角色和内容。
    此模型用于构建对话上下文，让 AI 能够理解之前的对话内容。
    
    属性:
        role (MessageRole): 消息的角色（用户、助手或系统）
        content (str): 消息的实际文本内容，必须至少包含一个字符
    """
    role: MessageRole  # 消息角色，指定此消息是来自用户、助手还是系统
    content: str = Field(
        ...,  # ... 表示此字段为必填项
        min_length=1,  # 最小长度为 1，确保内容不为空
        description="消息内容"  # 字段描述，用于 API 文档生成
    )  # 消息的实际文本内容


class ChatPayload(BaseModel):
    """
    Gemini 内容生成请求体数据模型
    
    定义客户端发送给服务器的请求数据结构，包含：
    - 当前用户输入的文本
    - 可选的系统提示（用于设定 AI 行为）
    - 对话历史记录（用于提供上下文）
    
    属性:
        text (str): 当前用户输入的提示词，必填，至少包含一个字符
        system_prompt (str | None): 可选的系统提示，用于设定 AI 的角色或行为模式
        history (List[ChatMessage]): 对话历史记录列表，按时间顺序排列，默认为空列表
    """

    text: str = Field(
        ...,  # 必填字段
        min_length=1,  # 最小长度为 1，确保不为空字符串
        description="需要生成内容的提示词"  # 字段描述
    )  # 当前用户输入的文本，这是 AI 需要处理的主要内容

    system_prompt: str | None = Field(
        None,  # 默认值为 None，表示此字段为可选
        description="可选的系统提示"  # 字段描述
    )  # 系统提示，用于设定 AI 的行为、角色或特殊指令，例如："你是一个专业的翻译助手"

    history: List[ChatMessage] = Field(
        default_factory=list,  # 使用 list 工厂函数创建默认空列表，避免可变默认参数问题
        description="对话上下文，顺序即为时间顺序"  # 字段描述
    )  # 历史对话记录列表，按时间顺序排列，用于提供对话上下文，帮助 AI 理解对话背景

class ChatResponse(BaseModel):
    """
    同步接口返回的响应数据模型
    
    定义同步内容生成端点的响应结构，包含：
    - 请求 ID（用于追踪和调试）
    - AI 生成的文本内容
    - 处理耗时（用于性能监控）
    
    属性:
        request_id (str): 唯一请求标识符，用于追踪和日志记录
        text (str): Gemini AI 生成的文本内容
        latency_ms (int): 请求处理耗时，单位为毫秒
    """
    request_id: str  # 用于追踪的请求 ID，每个请求都会生成唯一的 UUID
    text: str  # Gemini AI 生成的文本内容，这是用户请求的主要响应
    latency_ms: int  # 请求处理耗时（毫秒），用于性能监控和优化分析


def _normalize_text(payload: ChatPayload) -> str:
    """
    标准化输入文本
    
    去除用户输入文本的前后空白字符，确保不会传入空字符串。
    这是一个辅助函数，用于数据清理和验证。
    
    参数:
        payload (ChatPayload): 包含用户输入的请求体对象
    
    返回:
        str: 去除前后空白后的文本字符串
    
    注意:
        此函数只去除前后空白，不会去除中间的空白字符。
    """
    return payload.text.strip()  # 使用 strip() 方法去除字符串前后的空白字符（空格、换行符等）


def _compose_prompt(payload: ChatPayload) -> str:
    """
    组合完整的提示词（Prompt）
    
    将系统提示、历史对话记录和当前用户输入组合成一个完整的提示词字符串。
    这个函数负责构建发送给 Gemini API 的最终提示词。
    
    组合顺序：
    1. 系统提示（如果提供）
    2. 历史对话记录（按时间顺序）
    3. 当前用户输入
    
    格式：
    每个部分都用标签标记（[System]、[User]、[Assistant]），并用空行分隔。
    
    参数:
        payload (ChatPayload): 包含系统提示、历史记录和当前输入的请求体对象
    
    返回:
        str: 组合后的完整提示词字符串
    
    示例:
        输入：
        - system_prompt: "你是一个专业的翻译助手"
        - history: [{"role": "user", "content": "你好"}, {"role": "assistant", "content": "你好！"}]
        - text: "翻译：Hello"
        
        输出：
        [System]
        你是一个专业的翻译助手
        
        [User]
        你好
        
        [Assistant]
        你好！
        
        [User]
        翻译：Hello
    """
    segments: list[str] = []  # 存放分段文本的列表，每个元素代表提示词的一个部分
    
    # 如果提供了系统提示，将其添加到开头
    if payload.system_prompt:  # 检查系统提示是否存在且不为空
        # 使用 [System] 标签标记系统提示，并去除前后空白
        segments.append(f"[System]\n{payload.system_prompt.strip()}")

    # 遍历历史对话记录，按时间顺序添加到提示词中
    for message in payload.history:  # 遍历历史消息列表
        # 使用消息角色的首字母大写形式作为标签（User、Assistant、System）
        # 并去除消息内容的前后空白
        segments.append(f"[{message.role.capitalize()}]\n{message.content.strip()}")

    # 添加当前用户输入，这是最后一部分
    segments.append(f"[User]\n{_normalize_text(payload)}")  # 使用 _normalize_text 函数处理当前输入
    
    # 使用两个换行符（空行）连接所有部分，使提示词结构清晰易读
    return "\n\n".join(segments)


@router.post(  # 使用装饰器注册 POST 方法的端点
    "/content",  # 端点路径，完整路径为 /api/GoogleAI/content（包含路由前缀）
    response_model=ChatResponse,  # 指定响应数据模型，FastAPI 会自动验证和序列化响应
    summary="同步生成 Gemini 内容",  # API 文档摘要，显示在 Swagger UI 中
)
async def generate_content(
    payload: ChatPayload,  # 请求体，FastAPI 会自动解析 JSON 并验证数据
    client: GeminiClient = Depends(get_gemini_client)  # 依赖注入，自动获取 Gemini 客户端实例
) -> ChatResponse:
    """
    同步生成 Gemini AI 内容的端点
    
    此端点会等待 Gemini API 生成完整的响应后才返回结果。
    适合用于生成较短的内容或需要完整响应的场景。
    
    处理流程：
    1. 生成唯一请求 ID 用于追踪
    2. 组合完整的提示词（包含系统提示、历史记录和当前输入）
    3. 在线程池中调用 Gemini API（避免阻塞事件循环）
    4. 计算处理耗时
    5. 返回包含生成内容和元数据的响应
    
    参数:
        payload (ChatPayload): 包含用户输入、系统提示和历史记录的请求体
        client (GeminiClient): Gemini API 客户端实例，通过依赖注入自动提供
    
    返回:
        ChatResponse: 包含请求 ID、生成内容和耗时的响应对象
    
    异常:
        HTTPException 400: 输入验证失败或提示词为空
        HTTPException 502: Gemini API 调用失败
        HTTPException 500: 内部服务器错误
    
    注意:
        - 使用 anyio.to_thread.run_sync 在线程池中执行同步的 API 调用
        - 这确保了异步事件循环不会被阻塞，保持服务器的高并发性能
    """
    request_id = uuid.uuid4().hex  # 生成唯一的请求 ID（32 位十六进制字符串），用于追踪和日志记录
    logger.info("收到生成内容请求 - request_id=%s", request_id)  # 记录请求开始的日志
    
    try:
        # 组合完整的提示词，包含系统提示、历史记录和当前输入
        prompt = _compose_prompt(payload)
        
        # 验证提示词不为空
        if not prompt.strip():  # 检查去除空白后是否为空字符串
            raise HTTPException(
                status_code=400,  # HTTP 400 错误：客户端请求错误
                detail="请提供有效的输入内容。"  # 错误详情信息
            )

        started = time.perf_counter()  # 记录开始时间，使用高精度计时器（纳秒级精度）

        try:
            # 在线程池中执行同步的 Gemini API 调用
            # anyio.to_thread.run_sync 会将同步函数放到线程池中执行，避免阻塞异步事件循环
            text = await anyio.to_thread.run_sync(client.generate_text, prompt)
            
        except ValueError as exc:
            # 处理输入验证错误（例如：空字符串、无效格式等）
            logger.warning("输入验证失败 - request_id=%s, 错误: %s", request_id, exc)
            raise HTTPException(
                status_code=400,  # HTTP 400：客户端请求错误
                detail=str(exc)  # 将异常信息转换为字符串作为错误详情
            ) from exc  # 使用 from exc 保留原始异常链，便于调试
            
        except GeminiClientError as exc:
            # 处理 Gemini 客户端错误（例如：API 调用失败、网络错误等）
            logger.exception("Gemini 生成内容失败 - request_id=%s", request_id)  # 记录完整异常堆栈
            raise HTTPException(
                status_code=502,  # HTTP 502：网关错误，表示上游服务（Gemini API）不可用
                detail=str(exc)
            ) from exc
            
        except Exception as exc:
            # 捕获所有其他未预期的异常
            logger.exception("生成内容时发生未预期的错误 - request_id=%s", request_id)
            raise HTTPException(
                status_code=500,  # HTTP 500：内部服务器错误
                detail=f"内部错误: {str(exc)}"
            ) from exc

        # 计算处理耗时（毫秒）
        latency = int((time.perf_counter() - started) * 1000)  # 将纳秒转换为毫秒并取整
        logger.info("内容生成成功 - request_id=%s, 耗时: %dms", request_id, latency)  # 记录成功日志
        
        # 构造并返回响应对象
        return ChatResponse(
            request_id=request_id,  # 请求 ID
            text=text,  # AI 生成的文本内容
            latency_ms=latency  # 处理耗时（毫秒）
        )
        
    except HTTPException:
        # 重新抛出 HTTPException，让 FastAPI 的异常处理机制处理
        # 这样可以确保错误响应格式正确
        raise
        
    except Exception as exc:
        # 捕获所有其他异常（包括依赖注入阶段的错误）
        logger.exception("处理请求时发生未预期的错误 - request_id=%s", request_id)
        raise HTTPException(
            status_code=500,
            detail=f"内部错误: {str(exc)}"
        ) from exc


@router.post(  # 使用装饰器注册 POST 方法的端点
    "/stream",  # 端点路径，完整路径为 /api/GoogleAI/stream
    summary="以 SSE 方式串流 Gemini 回复",  # API 文档摘要
)
async def stream_content(
    payload: ChatPayload,  # 请求体，包含用户输入、系统提示和历史记录
    client: GeminiClient = Depends(get_gemini_client)  # 依赖注入的 Gemini 客户端实例
):
    """
    流式生成 Gemini AI 内容的端点（使用 Server-Sent Events）
    
    此端点使用 SSE（Server-Sent Events）技术，实时推送 AI 生成的内容片段。
    前端可以逐字或逐句接收并渲染内容，提供更好的用户体验。
    
    处理流程：
    1. 组合完整的提示词
    2. 验证提示词有效性
    3. 生成请求 ID
    4. 创建 SSE 事件流
    5. 在线程池中异步迭代 Gemini 的流式输出
    6. 将每个内容片段包装成 SSE 事件并推送给客户端
    
    SSE 事件格式：
    - message 事件：包含 AI 生成的内容片段
    - error 事件：包含错误信息
    - end 事件：表示流式传输完成
    
    参数:
        payload (ChatPayload): 包含用户输入、系统提示和历史记录的请求体
        client (GeminiClient): Gemini API 客户端实例
    
    返回:
        StreamingResponse: SSE 流式响应，媒体类型为 text/event-stream
    
    异常:
        HTTPException 400: 提示词为空或无效
    
    注意:
        - 使用 iterate_in_threadpool 在线程池中异步迭代同步生成器
        - SSE 格式要求每个事件以两个换行符结尾（\n\n）
        - 前端需要使用 EventSource API 来接收 SSE 事件
    """
    # 组合完整的提示词
    prompt = _compose_prompt(payload)
    
    # 验证提示词不为空
    if not prompt.strip():
        raise HTTPException(
            status_code=400,
            detail="请提供有效的输入内容。"
        )

    request_id = uuid.uuid4().hex  # 生成唯一请求 ID，用于标识此流式请求

    async def event_stream():
        """
        内部异步生成器函数，用于生成 SSE 事件流
        
        此函数会持续生成 SSE 事件，直到流式传输完成或发生错误。
        每个事件都遵循 SSE 格式规范。
        
        Yields:
            str: SSE 格式的事件字符串
        
        SSE 事件格式说明：
        - id: 事件 ID（可选，用于断线重连）
        - event: 事件类型（message、error、end）
        - data: 事件数据（实际内容）
        - 每个事件以两个换行符结尾（\n\n）
        """
        try:
            # 在线程池中异步迭代 Gemini 的流式输出
            # iterate_in_threadpool 将同步生成器转换为异步迭代器
            async for chunk in iterate_in_threadpool(client.stream_text(prompt)):
                # 生成 SSE message 事件，包含请求 ID 和内容片段
                # 格式：id: <request_id>\nevent: message\ndata: <chunk>\n\n
                yield f"id: {request_id}\nevent: message\ndata: {chunk}\n\n"
                
        except ValueError as exc:
            # 处理输入验证错误
            # 生成 SSE error 事件，通知前端发生错误
            yield f"event: error\ndata: {exc}\n\n"
            
        except GeminiClientError as exc:
            # 处理 Gemini API 错误
            logger.exception("Gemini 串流内容失败 - request_id=%s", request_id)
            # 生成 SSE error 事件
            yield f"event: error\ndata: {exc}\n\n"
            
        else:
            # 如果没有发生异常，生成结束事件
            # 前端可以通过监听 end 事件知道流式传输已完成
            yield f"id: {request_id}\nevent: end\ndata: [DONE]\n\n"

    # 返回 SSE 流式响应
    # media_type="text/event-stream" 指定响应类型为 SSE
    return StreamingResponse(
        event_stream(),  # 事件流生成器
        media_type="text/event-stream"  # SSE 的标准媒体类型
    )


def initGoogleAI(app, prefix=""):
    """
    初始化并注册 Google AI 路由到主 FastAPI 应用程序
    
    此函数是 Google AI 路由模块的入口点，负责将所有 Google AI 相关的端点
    注册到主应用程序中。
    
    参数:
        app (FastAPI): FastAPI 应用程序实例，路由将被注册到此实例
        prefix (str): 可选的路由前缀，默认为空字符串
                     如果提供，所有 Google AI 路由都会添加此前缀
                     例如：prefix="/api" 会使 /content 变成 /api/GoogleAI/content
    
    路由注册说明:
        - 此函数会将 router 中定义的所有端点注册到主应用
        - 路由前缀的组合顺序：prefix + router.prefix + endpoint_path
        - 例如：prefix="/api" + router.prefix="/GoogleAI" + "/content" = "/api/GoogleAI/content"
    
    使用示例:
        ```python
        from fastapi import FastAPI
        from src.router.googleAI.index import initGoogleAI
        
        app = FastAPI()
        initGoogleAI(app, prefix="/api")
        # 现在可以访问 /api/GoogleAI/content 和 /api/GoogleAI/stream
        ```
    
    注意:
        - 此函数应该在应用程序启动时调用一次
        - 通常由主路由模块（src.router.index）调用
    """
    # 将 Google AI 子路由注册到主应用程序
    # include_router 会将 router 中定义的所有端点添加到 app 中
    app.include_router(router, prefix=prefix)


# 定义模块的公共接口
# 当其他模块使用 from src.router.googleAI.index import * 时，只会导入此处列出的内容
# 这有助于控制模块的对外接口，避免导入不必要的内部实现（如辅助函数、数据模型等）
__all__ = ["initGoogleAI"]
