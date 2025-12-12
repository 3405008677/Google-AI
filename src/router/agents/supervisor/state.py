"""
Supervisor Architecture - State Definition

定义 LangGraph 的状态结构，用于在整个工作流中传递数据。

增强版本：
- 支持用户上下文（user_id, session_id, preferences）
- 支持任务规划（task_plan, current_step）
- 支持思考过程记录（thinking_steps）
"""

from typing import Annotated, List, TypedDict, Optional, Dict, Any, Sequence
from enum import Enum
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages as langgraph_add_messages


# 使用 LangGraph 内置的 add_messages，它更智能地处理消息合并
def add_messages(
    left: Sequence[BaseMessage], 
    right: Sequence[BaseMessage]
) -> List[BaseMessage]:
    """
    消息合并函数
    
    使用 LangGraph 内置的 add_messages 实现，支持：
    - 消息追加
    - 基于 ID 的消息更新
    - 消息去重
    """
    return langgraph_add_messages(left, right)


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"       # 等待执行
    IN_PROGRESS = "in_progress"  # 正在执行
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 执行失败
    SKIPPED = "skipped"       # 已跳过


class TaskStep(TypedDict, total=False):
    """任务步骤定义"""
    step_id: str              # 步骤 ID
    worker: str               # 执行的 Worker 名称
    description: str          # 步骤描述
    status: TaskStatus        # 步骤状态
    result: Optional[str]     # 执行结果
    error: Optional[str]      # 错误信息


class UserContext(TypedDict, total=False):
    """用户上下文信息"""
    user_id: Optional[str]         # 用户 ID
    session_id: Optional[str]      # 会话 ID
    language: str                  # 语言偏好（默认 "zh-CN"）
    timezone: str                  # 时区（默认 "Asia/Shanghai"）
    permissions: List[str]         # 权限列表
    preferences: Dict[str, Any]    # 用户偏好设置


class ThinkingStep(TypedDict, total=False):
    """思考步骤记录（用于流式输出）"""
    step_type: str            # 类型：planning, reasoning, decision, reflection
    content: str              # 思考内容
    timestamp: float          # 时间戳
    worker: Optional[str]     # 相关 Worker


class SupervisorState(TypedDict, total=False):
    """
    Supervisor Architecture 的状态定义
    
    使用 total=False 使所有字段变为可选，这样 Worker 可以只返回需要更新的字段。
    
    核心字段:
        messages: 消息历史，包含用户输入、Supervisor 决策、Worker 回复等
        next: Supervisor 决策的下一步动作（worker 名称或 "FINISH"）
        
    任务规划字段:
        task_plan: 任务规划列表，包含多个步骤
        current_step_index: 当前执行的步骤索引
        
    用户上下文:
        user_context: 用户信息和偏好设置
        
    执行追踪:
        current_worker: 当前正在执行的 worker 名称
        iteration_count: 当前迭代次数
        thinking_steps: 思考过程记录（用于流式输出）
        
    元数据:
        metadata: 额外的元数据，用于存储任务上下文、错误信息等
    """
    # ===== 核心字段 =====
    # 消息历史：存储所有对话消息（必需字段）
    messages: Annotated[List[BaseMessage], add_messages]
    
    # 下一步路由：Supervisor 决策的结果
    # 可以是 worker 名称（如 "Researcher", "DataAnalyst"）或 "FINISH"
    next: str
    
    # ===== 任务规划字段 =====
    # 任务规划：由 Supervisor 分解的任务步骤列表
    task_plan: List[TaskStep]
    
    # 当前步骤索引：正在执行的任务步骤
    current_step_index: int
    
    # 原始用户请求（保留原始问题）
    original_query: str
    
    # ===== 用户上下文 =====
    # 用户信息和偏好设置
    user_context: UserContext
    
    # ===== 执行追踪 =====
    # 当前执行的 worker（用于日志和调试）
    current_worker: Optional[str]
    
    # 迭代计数器：防止无限循环
    iteration_count: int
    
    # 思考步骤：记录 Supervisor 和 Worker 的思考过程（用于流式输出）
    thinking_steps: List[ThinkingStep]
    
    # ===== 元数据 =====
    # 元数据：存储任务上下文、错误信息、中间结果等
    metadata: Dict[str, Any]


# 默认用户上下文
DEFAULT_USER_CONTEXT: UserContext = {
    "user_id": None,
    "session_id": None,
    "language": "zh-CN",
    "timezone": "Asia/Shanghai",
    "permissions": [],
    "preferences": {},
}


# 默认状态值，用于初始化
DEFAULT_STATE: SupervisorState = {
    "messages": [],
    "next": "",
    "task_plan": [],
    "current_step_index": 0,
    "original_query": "",
    "user_context": DEFAULT_USER_CONTEXT,
    "current_worker": None,
    "iteration_count": 0,
    "thinking_steps": [],
    "metadata": {},
}


# 最大迭代次数，防止无限循环
MAX_ITERATIONS = 10

# 最大任务步骤数
MAX_TASK_STEPS = 8


def create_thinking_step(
    step_type: str,
    content: str,
    worker: Optional[str] = None,
) -> ThinkingStep:
    """
    创建思考步骤记录
    
    Args:
        step_type: 类型（planning, reasoning, decision, reflection）
        content: 思考内容
        worker: 相关 Worker 名称（可选）
        
    Returns:
        ThinkingStep 字典
    """
    import time
    return {
        "step_type": step_type,
        "content": content,
        "timestamp": time.time(),
        "worker": worker,
    }


def create_task_step(
    step_id: str,
    worker: str,
    description: str,
    status: TaskStatus = TaskStatus.PENDING,
) -> TaskStep:
    """
    创建任务步骤
    
    Args:
        step_id: 步骤 ID
        worker: 执行的 Worker 名称
        description: 步骤描述
        status: 初始状态（默认 PENDING）
        
    Returns:
        TaskStep 字典
    """
    return {
        "step_id": step_id,
        "worker": worker,
        "description": description,
        "status": status,
        "result": None,
        "error": None,
    }
