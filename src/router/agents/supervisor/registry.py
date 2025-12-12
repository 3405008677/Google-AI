"""
Supervisor Architecture - Worker Registry

Worker 注册表，管理所有可用的专家团队（Layer 4）。
支持：
- 动态注册和查找 Worker
- 子图（Subgraph）Worker
- 工具调用 Worker
"""

from typing import Dict, Optional, List, Any, TYPE_CHECKING, Union
from abc import ABC, abstractmethod
from enum import Enum
import threading
from langchain_core.messages import AIMessage, BaseMessage
from src.server.logging_setup import logger

if TYPE_CHECKING:
    from src.router.agents.supervisor.state import SupervisorState


class WorkerType(str, Enum):
    """Worker 类型枚举"""
    SIMPLE = "simple"           # 简单 Worker（直接执行）
    TOOL_BASED = "tool_based"   # 基于工具的 Worker
    SUBGRAPH = "subgraph"       # 子图 Worker（内部有自己的 LangGraph）
    LLM_POWERED = "llm_powered" # LLM 驱动的 Worker


class Worker(ABC):
    """
    Worker 基类
    
    所有专家（Layer 4）都应该继承此类并实现 execute 方法。
    
    支持的 Worker 类型：
    - SIMPLE: 简单任务，直接执行
    - TOOL_BASED: 基于工具调用的任务
    - SUBGRAPH: 复杂任务，有自己的子图
    - LLM_POWERED: 使用 LLM 进行推理的任务
    """
    
    def __init__(
        self, 
        name: str, 
        description: str, 
        priority: int = 0,
        worker_type: WorkerType = WorkerType.SIMPLE,
        tools: Optional[List[Any]] = None,
    ):
        """
        初始化 Worker
        
        Args:
            name: Worker 名称（唯一标识符）
            description: Worker 的描述，用于 Supervisor 决策
            priority: 优先级（数值越大优先级越高），用于排序
            worker_type: Worker 类型
            tools: 可用的工具列表（用于 TOOL_BASED 类型）
        """
        self.name = name
        self.description = description
        self.priority = priority
        self.worker_type = worker_type
        self.tools = tools or []
        self._execution_count = 0
    
    @abstractmethod
    async def execute(self, state: "SupervisorState") -> Dict[str, Any]:
        """
        执行 Worker 的任务
        
        Args:
            state: 当前状态
            
        Returns:
            更新后的状态字典，通常包含新的消息
        """
        pass
    
    def get_stats(self) -> Dict[str, Any]:
        """获取 Worker 的统计信息"""
        return {
            "name": self.name,
            "description": self.description,
            "priority": self.priority,
            "worker_type": self.worker_type.value,
            "execution_count": self._execution_count,
            "tools_count": len(self.tools),
        }
    
    def __repr__(self) -> str:
        return f"Worker(name={self.name}, type={self.worker_type.value}, priority={self.priority})"


class BaseWorkerMixin:
    """
    Worker 基础功能混入类
    
    提供常用的辅助方法，减少重复代码。
    包括：
    - 消息提取辅助方法
    - 状态访问辅助方法
    - 标准响应创建方法
    """
    
    @staticmethod
    def get_last_user_query(messages: List[BaseMessage]) -> Optional[str]:
        """
        获取最后一条用户消息的内容
        
        Args:
            messages: 消息列表
            
        Returns:
            最后一条用户消息的内容，如果没有找到则返回最后一条消息
        """
        if not messages:
            return None
        
        # 优先查找用户消息
        from langchain_core.messages import HumanMessage
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                return msg.content if hasattr(msg, 'content') else str(msg)
        
        # 如果没有用户消息，返回最后一条消息
        last_message = messages[-1]
        return last_message.content if hasattr(last_message, 'content') else str(last_message)
    
    @staticmethod
    def get_original_query(state: Dict[str, Any]) -> Optional[str]:
        """
        获取原始用户查询
        
        Args:
            state: 状态字典
            
        Returns:
            原始查询内容
        """
        # 优先使用保存的原始查询
        original_query = state.get("original_query")
        if original_query:
            return original_query
        
        # 回退到消息列表中的第一条用户消息
        messages = state.get("messages", [])
        from langchain_core.messages import HumanMessage
        for msg in messages:
            if isinstance(msg, HumanMessage):
                return msg.content if hasattr(msg, 'content') else str(msg)
        
        return None
    
    @staticmethod
    def get_worker_outputs(messages: List[BaseMessage]) -> List[Dict[str, str]]:
        """
        收集所有 Worker 的输出
        
        Args:
            messages: 消息列表
            
        Returns:
            Worker 输出列表，每个元素包含 name 和 content
        """
        outputs = []
        for msg in messages:
            if isinstance(msg, AIMessage) and hasattr(msg, 'name') and msg.name:
                outputs.append({
                    "name": msg.name,
                    "content": msg.content,
                })
        return outputs
    
    @staticmethod
    def get_user_context(state: Dict[str, Any]) -> Dict[str, Any]:
        """
        获取用户上下文信息
        
        Args:
            state: 状态字典
            
        Returns:
            用户上下文字典
        """
        return state.get("user_context", {})
    
    @staticmethod
    def get_current_task_step(state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        获取当前任务步骤
        
        Args:
            state: 状态字典
            
        Returns:
            当前任务步骤，如果没有则返回 None
        """
        task_plan = state.get("task_plan", [])
        current_index = state.get("current_step_index", 0)
        
        if 0 <= current_index < len(task_plan):
            return task_plan[current_index]
        return None
    
    @staticmethod
    def create_worker_response(
        worker_name: str,
        content: str,
        state: Dict[str, Any],
        thinking_step: Optional[Dict[str, Any]] = None,
        mark_task_completed: bool = True,
        task_status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        创建标准化的 Worker 响应
        
        这是一个统一的响应创建方法，消除各个 Worker 中的重复代码。
        
        Args:
            worker_name: Worker 名称
            content: 响应内容
            state: 当前状态字典
            thinking_step: 可选的思考步骤记录
            mark_task_completed: 是否标记当前任务步骤为已完成
            task_status: 自定义任务状态（覆盖 mark_task_completed）
            
        Returns:
            格式化的响应字典，包含 messages、current_worker、task_plan 等
        """
        from src.router.agents.supervisor.state import TaskStatus
        
        result: Dict[str, Any] = {
            "messages": [AIMessage(content=content, name=worker_name)],
            "current_worker": worker_name,
        }
        
        # 添加思考步骤（如果有）
        if thinking_step:
            existing_steps = state.get("thinking_steps", [])
            result["thinking_steps"] = existing_steps + [thinking_step]
        
        # 更新任务步骤状态
        task_plan = state.get("task_plan", [])
        current_index = state.get("current_step_index", 0)
        
        if task_plan and 0 <= current_index < len(task_plan):
            # 深拷贝 task_plan 避免修改原始数据
            task_plan = [step.copy() for step in task_plan]
            current_step = task_plan[current_index]
            
            # 设置状态
            if task_status:
                current_step["status"] = task_status
            elif mark_task_completed:
                current_step["status"] = TaskStatus.COMPLETED
            
            # 保存结果摘要
            max_result_length = 200
            current_step["result"] = (
                content[:max_result_length] + "..." 
                if len(content) > max_result_length 
                else content
            )
            
            result["task_plan"] = task_plan
            result["current_step_index"] = current_index + 1
        
        return result
    
    @staticmethod
    def create_error_response(
        worker_name: str,
        error_message: str,
        state: Dict[str, Any],
        error_detail: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        创建错误响应
        
        Args:
            worker_name: Worker 名称
            error_message: 错误消息
            state: 当前状态字典
            error_detail: 详细错误信息
            
        Returns:
            格式化的错误响应字典
        """
        from src.router.agents.supervisor.state import TaskStatus
        
        content = f"执行失败: {error_message}"
        if error_detail:
            content += f"\n详细信息: {error_detail}"
        
        result: Dict[str, Any] = {
            "messages": [AIMessage(content=content, name=worker_name)],
            "current_worker": worker_name,
            "metadata": {
                **state.get("metadata", {}),
                "error": error_message,
                "error_type": f"{worker_name.lower()}_execution_error",
            },
        }
        
        # 更新任务步骤状态为失败
        task_plan = state.get("task_plan", [])
        current_index = state.get("current_step_index", 0)
        
        if task_plan and 0 <= current_index < len(task_plan):
            task_plan = [step.copy() for step in task_plan]
            task_plan[current_index]["status"] = TaskStatus.FAILED
            task_plan[current_index]["error"] = error_message
            result["task_plan"] = task_plan
        
        return result


class SubgraphWorker(Worker):
    """
    子图 Worker 基类
    
    用于封装具有自己工作流的复杂任务，如数据分析团队。
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        priority: int = 0,
    ):
        super().__init__(
            name=name,
            description=description,
            priority=priority,
            worker_type=WorkerType.SUBGRAPH,
        )
        self._subgraph = None
    
    @abstractmethod
    def build_subgraph(self):
        """
        构建子图
        
        子类需要实现此方法来定义子图的工作流。
        
        Returns:
            编译后的 LangGraph 应用
        """
        pass
    
    @property
    def subgraph(self):
        """延迟初始化子图"""
        if self._subgraph is None:
            self._subgraph = self.build_subgraph()
        return self._subgraph
    
    async def execute(self, state: "SupervisorState") -> Dict[str, Any]:
        """执行子图"""
        logger.info(f"🔄 [{self.name}] 开始执行子图...")
        self._execution_count += 1
        
        try:
            # 准备子图输入
            subgraph_input = self.prepare_subgraph_input(state)
            
            # 执行子图
            result = await self.run_subgraph(subgraph_input)
            
            # 处理子图输出
            return self.process_subgraph_output(result, state)
            
        except Exception as e:
            logger.error(f"[{self.name}] 子图执行失败: {e}", exc_info=True)
            return {
                "messages": [AIMessage(
                    content=f"执行失败: {str(e)}",
                    name=self.name
                )],
                "current_worker": self.name,
                "metadata": {
                    **state.get("metadata", {}),
                    "error": str(e),
                    "error_type": "subgraph_execution_error"
                }
            }
    
    def prepare_subgraph_input(self, state: "SupervisorState") -> Dict[str, Any]:
        """
        准备子图输入
        
        子类可以重写此方法来自定义输入。
        """
        messages = state.get("messages", [])
        # 获取最后一条用户消息作为问题
        question = ""
        from langchain_core.messages import HumanMessage
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                question = msg.content
                break
        
        return {
            "messages": [],
            "question": question,
        }
    
    async def run_subgraph(self, subgraph_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        运行子图
        
        子类可以重写此方法来自定义执行逻辑。
        """
        final_state = None
        async for event in self.subgraph.astream(subgraph_input):
            for node_name, node_output in event.items():
                final_state = node_output
                logger.debug(f"[{self.name}] 子图节点 {node_name} 输出: {node_output}")
        
        return final_state or {}
    
    def process_subgraph_output(
        self, 
        result: Dict[str, Any], 
        parent_state: "SupervisorState"
    ) -> Dict[str, Any]:
        """
        处理子图输出
        
        将子图的输出转换为父图可以使用的格式。
        子类可以重写此方法来自定义输出处理。
        """
        # 获取子图的消息输出
        messages = result.get("messages", [])
        if not messages:
            # 如果没有消息，创建一个默认消息
            messages = [AIMessage(
                content="子图执行完成，但没有输出。",
                name=self.name
            )]
        
        return {
            "messages": messages,
            "current_worker": self.name,
        }


class ToolWorker(Worker):
    """
    工具调用 Worker 基类
    
    用于封装基于工具调用的任务。
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        tools: List[Any],
        priority: int = 0,
    ):
        super().__init__(
            name=name,
            description=description,
            priority=priority,
            worker_type=WorkerType.TOOL_BASED,
            tools=tools,
        )
    
    async def execute(self, state: "SupervisorState") -> Dict[str, Any]:
        """执行工具调用"""
        logger.info(f"🛠️ [{self.name}] 开始执行工具调用...")
        self._execution_count += 1
        
        # 子类需要实现具体的工具调用逻辑
        raise NotImplementedError("子类需要实现 execute 方法")


class WorkerRegistry:
    """
    Worker 注册表
    
    线程安全的单例模式，管理所有注册的 Worker。
    """
    
    _instance: Optional['WorkerRegistry'] = None
    _lock: threading.Lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                # 双重检查锁定
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._workers: Dict[str, Worker] = {}
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance
    
    def register(self, worker: Worker, replace: bool = False) -> None:
        """
        注册一个 Worker
        
        Args:
            worker: 要注册的 Worker 实例
            replace: 如果为 True，允许替换已存在的 Worker
            
        Raises:
            ValueError: 如果 Worker 名称已存在且 replace=False
        """
        if worker.name in self._workers and not replace:
            logger.warning(f"Worker '{worker.name}' 已经注册，跳过")
            return
        
        self._workers[worker.name] = worker
        logger.info(f"{'替换' if replace else '注册'} Worker: {worker.name} [{worker.worker_type.value}] - {worker.description}")
    
    def get(self, name: str) -> Optional[Worker]:
        """
        根据名称获取 Worker
        
        Args:
            name: Worker 名称
            
        Returns:
            Worker 实例，如果不存在则返回 None
        """
        return self._workers.get(name)
    
    def get_all(self) -> Dict[str, Worker]:
        """
        获取所有注册的 Worker
        
        Returns:
            Worker 字典，key 为名称，value 为 Worker 实例
        """
        return self._workers.copy()
    
    def get_by_type(self, worker_type: WorkerType) -> List[Worker]:
        """
        按类型获取 Worker 列表
        
        Args:
            worker_type: Worker 类型
            
        Returns:
            指定类型的 Worker 列表
        """
        return [w for w in self._workers.values() if w.worker_type == worker_type]
    
    def get_names(self) -> List[str]:
        """
        获取所有 Worker 的名称列表（按优先级排序）
        
        Returns:
            Worker 名称列表
        """
        sorted_workers = sorted(
            self._workers.values(), 
            key=lambda w: w.priority, 
            reverse=True
        )
        return [w.name for w in sorted_workers]
    
    def get_descriptions(self) -> Dict[str, str]:
        """
        获取所有 Worker 的名称和描述
        
        Returns:
            字典，key 为 Worker 名称，value 为描述
        """
        return {name: worker.description for name, worker in self._workers.items()}
    
    def get_formatted_descriptions(self) -> str:
        """
        获取格式化的 Worker 描述列表
        
        Returns:
            格式化的字符串，每行一个 Worker
        """
        sorted_workers = sorted(
            self._workers.values(), 
            key=lambda w: w.priority, 
            reverse=True
        )
        return "\n".join([
            f"- {w.name} [{w.worker_type.value}]: {w.description}" 
            for w in sorted_workers
        ])
    
    def unregister(self, name: str) -> bool:
        """
        注销一个 Worker
        
        Args:
            name: Worker 名称
            
        Returns:
            是否成功注销
        """
        if name in self._workers:
            del self._workers[name]
            logger.info(f"已注销 Worker: {name}")
            return True
        return False
    
    def clear(self) -> None:
        """清空所有注册的 Worker"""
        self._workers.clear()
        logger.info("已清空所有 Worker")
    
    def is_empty(self) -> bool:
        """检查注册表是否为空"""
        return len(self._workers) == 0
    
    def count(self) -> int:
        """获取注册的 Worker 数量"""
        return len(self._workers)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取注册表统计信息"""
        type_counts = {}
        for worker in self._workers.values():
            type_name = worker.worker_type.value
            type_counts[type_name] = type_counts.get(type_name, 0) + 1
        
        return {
            "total_workers": self.count(),
            "type_distribution": type_counts,
            "workers": [w.get_stats() for w in self._workers.values()],
        }


def get_registry() -> WorkerRegistry:
    """获取全局 Worker 注册表实例"""
    return WorkerRegistry()


def register_worker(worker: Worker, replace: bool = False) -> None:
    """
    便捷函数：注册一个 Worker
    
    Args:
        worker: 要注册的 Worker 实例
        replace: 如果为 True，允许替换已存在的 Worker
    """
    get_registry().register(worker, replace=replace)


def get_worker(name: str) -> Optional[Worker]:
    """
    便捷函数：获取一个 Worker
    
    Args:
        name: Worker 名称
        
    Returns:
        Worker 实例，如果不存在则返回 None
    """
    return get_registry().get(name)
