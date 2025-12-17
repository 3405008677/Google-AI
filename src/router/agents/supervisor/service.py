"""
Supervisor Architecture - Service Layer

服务层，提供 Supervisor Architecture 的 API 接口。

功能：
1. 流式和非流式调用
2. 集成 Performance Layer（语义缓存 + 规则引擎）
3. 支持用户上下文注入
4. 增强的流式事件输出（包含思考过程）
"""

import time
import json
from typing import AsyncIterator, Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.base import BaseCheckpointSaver
from src.router.agents.supervisor.workflow import get_graph_app
from src.router.agents.supervisor.supervisor import SupervisorConfig
from src.router.agents.supervisor.state import (
    SupervisorState, 
    DEFAULT_STATE,
    DEFAULT_USER_CONTEXT,
    UserContext,
)
from src.server.logging_setup import logger


class StreamEventType(str, Enum):
    """
    流式事件类型（极简版）
    
    只关注重要内容，不暴露内部处理细节
    """
    START = "start"          # 开始处理
    PROGRESS = "progress"    # 处理进度（可选）
    ANSWER = "answer"        # 答案/结果
    DONE = "done"            # 完成
    ERROR = "error"          # 错误


@dataclass
class StreamEvent:
    """
    流式事件（极简版）
    
    只返回用户关心的内容：
    - type: 事件类型
    - content: 内容（可选）
    - progress: 进度（可选）
    """
    type: StreamEventType
    content: str = ""                                # 内容
    progress: Optional[Dict[str, int]] = None        # {"current": x, "total": y}
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典
        
        返回格式示例：
        {"type": "answer", "content": "这是答案..."}
        {"type": "progress", "progress": {"current": 1, "total": 2}}
        {"type": "done"}
        """
        result: Dict[str, Any] = {
            "type": self.type.value if isinstance(self.type, StreamEventType) else self.type,
        }
        
        if self.content:
            result["content"] = self.content
        if self.progress:
            result["progress"] = self.progress
        
        return result
    
    def to_sse(self) -> str:
        """转换为 SSE 格式"""
        data = json.dumps(self.to_dict(), ensure_ascii=False)
        return f"data: {data}\n\n"


class SupervisorService:
    """
    Supervisor Architecture 服务类
    
    提供统一的接口来调用 Supervisor Architecture。
    
    特性：
    - 集成 Performance Layer（可选）
    - 支持用户上下文注入
    - 增强的流式输出（SSE 格式）
    - 思考过程实时推送
    """
    
    def __init__(
        self,
        checkpointer: Optional[BaseCheckpointSaver] = None,
        supervisor_config: Optional[SupervisorConfig] = None,
        enable_performance_layer: bool = True,
    ):
        """
        初始化服务
        
        Args:
            checkpointer: 可选的检查点存储器，用于保存对话历史
            supervisor_config: 可选的 Supervisor 配置
            enable_performance_layer: 是否启用速通优化层
        """
        self.checkpointer = checkpointer
        self.supervisor_config = supervisor_config
        self.enable_performance_layer = enable_performance_layer
        self._graph_app = None
        self._performance_layer = None
    
    @property
    def graph_app(self):
        """获取图应用实例（延迟初始化）"""
        if self._graph_app is None:
            self._graph_app = get_graph_app(
                checkpointer=self.checkpointer,
                supervisor_config=self.supervisor_config,
            )
        return self._graph_app
    
    @property
    def performance_layer(self):
        """获取 Performance Layer 实例（延迟初始化）"""
        if self._performance_layer is None and self.enable_performance_layer:
            try:
                from src.router.agents.performance_layer import get_performance_layer
                self._performance_layer = get_performance_layer()
            except ImportError:
                logger.warning("Performance Layer 导入失败，将禁用速通优化")
                self._performance_layer = None
        return self._performance_layer
    
    def _build_initial_state(
        self,
        user_message: str,
        user_context: Optional[UserContext] = None,
        initial_state: Optional[Dict[str, Any]] = None,
    ) -> SupervisorState:
        """
        构建初始状态
        
        Args:
            user_message: 用户消息
            user_context: 用户上下文信息
            initial_state: 可选的初始状态
            
        Returns:
            初始状态字典
        """
        # 合并用户上下文
        context = {**DEFAULT_USER_CONTEXT}
        if user_context:
            context.update(user_context)
        
        return {
            **DEFAULT_STATE,
            "messages": [HumanMessage(content=user_message)],
            "original_query": user_message,
            "user_context": context,
            "metadata": initial_state.get("metadata", {}) if initial_state else {},
        }
    
    def _build_config(self, thread_id: str) -> Dict[str, Any]:
        """构建 LangGraph 配置"""
        return {"configurable": {"thread_id": thread_id}}
    
    def _parse_node_output(
        self,
        node_name: str,
        node_output: Dict[str, Any],
        prev_state: Optional[Dict[str, Any]] = None,
    ) -> List[StreamEvent]:
        """
        解析节点输出（极简版）
        
        只返回重要内容：
        - 实际的答案/结果 (ANSWER)
        - 进度更新 (PROGRESS) - 可选
        
        不返回：
        - 谁在处理
        - 内部决策过程
        - 任务规划细节
        """
        events = []
        
        # 计算进度（可选）
        task_plan = node_output.get("task_plan", prev_state.get("task_plan", []) if prev_state else [])
        progress = None
        if task_plan:
            from src.router.agents.supervisor.state import TaskStatus
            completed = sum(1 for step in task_plan if step.get("status") in [TaskStatus.COMPLETED, TaskStatus.SKIPPED])
            total = len(task_plan)
            if total > 1:  # 只有多步骤任务才显示进度
                progress = {"current": completed, "total": total}
        
        # 只关注 Worker 输出的实际内容
        if "messages" in node_output and node_name != "supervisor":
            messages = node_output.get("messages", [])
            if messages:
                last_message = messages[-1]
                content = (
                    last_message.content 
                    if hasattr(last_message, 'content') 
                    else str(last_message)
                )
                
                # 发送答案
                events.append(StreamEvent(
                    type=StreamEventType.ANSWER,
                    content=content,
                    progress=progress,
                ))
        
        # 多步骤任务：发送进度更新（不含内容）
        elif node_name == "supervisor" and progress and progress["current"] > 0:
            events.append(StreamEvent(
                type=StreamEventType.PROGRESS,
                progress=progress,
            ))
        
        return events
    
    async def run(
        self,
        user_message: str,
        thread_id: str = "default",
        user_context: Optional[UserContext] = None,
        initial_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        非流式运行 Supervisor Architecture
        
        Args:
            user_message: 用户消息
            thread_id: 线程 ID，用于区分不同的对话会话
            user_context: 用户上下文信息
            initial_state: 可选的初始状态
            
        Returns:
            最终状态字典
        """
        # 1. 检查 Performance Layer
        if self.performance_layer:
            cache_result = self.performance_layer.process_query(user_message)
            if cache_result:
                logger.info(f"速通层命中 | 来源: {cache_result.get('source')}")
                return {
                    "answer": cache_result.get("answer"),
                    "source": cache_result.get("source"),
                    "cached": True,
                }
        
        # 2. 构建初始状态
        inputs = self._build_initial_state(user_message, user_context, initial_state)
        config = self._build_config(thread_id)
        
        logger.info(f"开始运行 Supervisor (thread: {thread_id})")
        
        final_state = None
        try:
            async for event in self.graph_app.astream(inputs, config=config):
                for node_name, node_output in event.items():
                    final_state = node_output
        except Exception as e:
            logger.error(f"运行 Supervisor 时出错: {e}", exc_info=True)
            return {
                "error": str(e),
                "error_type": "execution_error",
            }
        
        # 3. 缓存结果
        if self.performance_layer and final_state:
            messages = final_state.get("messages", [])
            if messages:
                last_message = messages[-1]
                answer = last_message.content if hasattr(last_message, 'content') else str(last_message)
                self.performance_layer.cache_answer(user_message, answer)
        
        logger.info(f"Supervisor 运行完成 (thread: {thread_id})")
        return final_state or {}
    
    async def run_stream(
        self,
        user_message: str,
        thread_id: str = "default",
        user_context: Optional[UserContext] = None,
        initial_state: Optional[Dict[str, Any]] = None,
        sse_format: bool = False,
    ) -> AsyncIterator[Dict[str, Any] | str]:
        """
        流式运行 Supervisor Architecture
        
        每个节点执行完后立即返回结果，支持实时反馈思考过程。
        
        Args:
            user_message: 用户消息
            thread_id: 线程 ID，用于区分不同的对话会话
            user_context: 用户上下文信息
            initial_state: 可选的初始状态
            sse_format: 是否返回 SSE 格式字符串（用于 FastAPI StreamingResponse）
            
        Yields:
            事件字典或 SSE 格式字符串
        """
        # 发送开始事件
        start_event = StreamEvent(type=StreamEventType.START)
        yield start_event.to_sse() if sse_format else start_event.to_dict()
        
        # 1. 检查缓存
        if self.performance_layer:
            cache_result = self.performance_layer.process_query(user_message)
            if cache_result:
                # 直接发送答案
                answer_event = StreamEvent(
                    type=StreamEventType.ANSWER,
                    content=cache_result.get("answer"),
                )
                yield answer_event.to_sse() if sse_format else answer_event.to_dict()
                
                done_event = StreamEvent(type=StreamEventType.DONE)
                yield done_event.to_sse() if sse_format else done_event.to_dict()
                return
        
        # 2. 构建初始状态
        inputs = self._build_initial_state(user_message, user_context, initial_state)
        config = self._build_config(thread_id)
        
        logger.info(f"开始流式运行 Supervisor (thread: {thread_id})")
        
        prev_state = inputs
        final_answer = ""
        
        try:
            async for event in self.graph_app.astream(
                inputs, 
                config=config, 
                stream_mode="updates"
            ):
                for node_name, node_output in event.items():
                    # 解析节点输出为事件
                    stream_events = self._parse_node_output(node_name, node_output, prev_state)
                    
                    for stream_event in stream_events:
                        yield stream_event.to_sse() if sse_format else stream_event.to_dict()
                    
                    # 更新前一状态
                    prev_state = {**prev_state, **node_output}
                    
                    # 记录最终答案
                    if "messages" in node_output and node_output["messages"]:
                        last_msg = node_output["messages"][-1]
                        final_answer = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
                        
        except Exception as e:
            logger.error(f"流式运行 Supervisor 时出错: {e}", exc_info=True)
            error_event = StreamEvent(
                type=StreamEventType.ERROR,
                content=str(e),
            )
            yield error_event.to_sse() if sse_format else error_event.to_dict()
            return
        
        # 3. 缓存结果
        if self.performance_layer and final_answer:
            self.performance_layer.cache_answer(user_message, final_answer)
        
        # 完成
        done_event = StreamEvent(type=StreamEventType.DONE)
        yield done_event.to_sse() if sse_format else done_event.to_dict()
        
        logger.info(f"Supervisor 流式运行完成 (thread: {thread_id})")
    
    async def get_state(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定线程的当前状态
        
        Args:
            thread_id: 线程 ID
            
        Returns:
            状态字典，如果不存在则返回 None
        """
        if not self.checkpointer:
            logger.warning("未配置 checkpointer，无法获取状态")
            return None
        
        try:
            config = self._build_config(thread_id)
            state = await self.graph_app.aget_state(config)
            return state.values if state else None
        except Exception as e:
            logger.error(f"获取状态时出错: {e}", exc_info=True)
            return None
    
    async def get_history(self, thread_id: str) -> Optional[list]:
        """
        获取指定线程的对话历史
        
        Args:
            thread_id: 线程 ID
            
        Returns:
            消息列表，如果不存在则返回 None
        """
        state = await self.get_state(thread_id)
        if state:
            return state.get("messages", [])
        return None
    
    def reset_graph(self) -> None:
        """重置图应用实例"""
        self._graph_app = None
        logger.info("已重置服务的图应用实例")


# 全局服务实例（单例模式）
_service_instance: Optional[SupervisorService] = None


def get_service(
    checkpointer: Optional[BaseCheckpointSaver] = None,
    supervisor_config: Optional[SupervisorConfig] = None,
    enable_performance_layer: bool = True,
) -> SupervisorService:
    """
    获取全局 SupervisorService 实例
    
    Args:
        checkpointer: 可选的检查点存储器
        supervisor_config: 可选的 Supervisor 配置
        enable_performance_layer: 是否启用速通优化层
        
    Returns:
        SupervisorService 实例
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = SupervisorService(
            checkpointer=checkpointer,
            supervisor_config=supervisor_config,
            enable_performance_layer=enable_performance_layer,
        )
    return _service_instance


def reset_service() -> None:
    """重置全局服务实例"""
    global _service_instance
    _service_instance = None
    logger.info("已重置全局服务实例")
