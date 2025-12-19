"""
Supervisor Architecture - LangGraph Workflow

构建 LangGraph 工作流，连接 Supervisor 和所有 Worker。
"""

from typing import Optional, Dict, Any, Callable
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.base import BaseCheckpointSaver
from src.router.agents.supervisor.state import SupervisorState
from src.router.agents.supervisor.supervisor import create_supervisor_node, SupervisorConfig
from src.router.agents.supervisor.registry import get_registry
from src.server.logging_setup import logger


def build_worker_node(worker_name: str) -> Callable[[SupervisorState], Dict[str, Any]]:
    """
    为指定的 Worker 创建一个节点函数
    
    Args:
        worker_name: Worker 名称
        
    Returns:
        一个异步函数，接受 SupervisorState 并返回更新后的状态
    """
    async def worker_node(state: SupervisorState) -> Dict[str, Any]:
        """Worker 节点函数"""
        registry = get_registry()
        worker = registry.get(worker_name)
        
        if not worker:
            logger.error(f"Worker '{worker_name}' 未找到")
            return {
                "messages": [],
                "current_worker": worker_name,
                "metadata": {
                    **state.get("metadata", {}),
                    "error": f"Worker '{worker_name}' 未找到",
                    "error_type": "worker_not_found"
                }
            }
        
        try:
            # 显示调用的 Worker 信息
            worker_desc = worker.description if hasattr(worker, 'description') else "未知"
            logger.info(f"🤖 [Agent调用] 正在调用 Worker: {worker_name} | 描述: {worker_desc}")
            logger.info(f"   └─ Worker类型: {worker.worker_type.value if hasattr(worker, 'worker_type') else '未知'}")
            
            updated_state = await worker.execute(state)
            
            # 显示 Worker 执行完成
            logger.info(f"✅ [Agent完成] Worker '{worker_name}' 执行完成")
            return updated_state
        except Exception as e:
            logger.error(f"Worker '{worker_name}' 执行时出错: {e}", exc_info=True)
            return {
                "messages": [],
                "current_worker": worker_name,
                "metadata": {
                    **state.get("metadata", {}),
                    "error": str(e),
                    "error_type": "worker_execution_error"
                }
            }
    
    return worker_node


def build_graph(
    checkpointer: Optional[BaseCheckpointSaver] = None,
    supervisor_config: Optional[SupervisorConfig] = None,
) -> StateGraph:
    """
    构建 LangGraph 工作流
    
    Args:
        checkpointer: 可选的检查点存储器，用于保存对话历史
                     如果为 None，则使用内存存储器
        supervisor_config: 可选的 Supervisor 配置
    
    Returns:
        编译后的 LangGraph 应用
    """
    logger.info("开始构建 Supervisor Architecture 工作流...")
    
    # 获取所有注册的 Worker
    registry = get_registry()
    workers = registry.get_all()
    
    if not workers:
        logger.warning("没有注册任何 Worker，工作流可能无法正常工作")
    
    # 创建图对象
    workflow = StateGraph(SupervisorState)
    
    # 添加 Supervisor 节点
    supervisor_node = create_supervisor_node(config=supervisor_config)
    workflow.add_node("supervisor", supervisor_node)
    logger.info("✓ 已添加 Supervisor 节点")
    
    # 添加所有 Worker 节点
    for worker_name in workers.keys():
        workflow.add_node(worker_name, build_worker_node(worker_name))
        logger.info(f"✓ 已添加 Worker 节点: {worker_name}")
    
    # 设置边（Edges）
    # 1. 所有 Worker 完成后都回到 Supervisor 汇报
    for worker_name in workers.keys():
        workflow.add_edge(worker_name, "supervisor")
    
    # 2. Supervisor 根据决策结果路由到对应的 Worker 或结束
    def route_decision(state: SupervisorState) -> str:
        """路由决策函数"""
        next_action = state.get("next", "FINISH")
        
        # 验证路由目标是否存在
        if next_action != "FINISH" and next_action not in workers:
            logger.warning(f"路由目标 '{next_action}' 不存在，强制结束")
            return "FINISH"
        
        return next_action
    
    # 构建路由映射
    route_map: Dict[str, str] = {"FINISH": END}
    for worker_name in workers.keys():
        route_map[worker_name] = worker_name
    
    workflow.add_conditional_edges(
        "supervisor",
        route_decision,
        route_map
    )
    
    # 设置入口点
    workflow.set_entry_point("supervisor")
    
    # 编译图
    if checkpointer is None:
        checkpointer = MemorySaver()
    
    compiled_graph = workflow.compile(checkpointer=checkpointer)
    
    logger.info(f"✓ Supervisor Architecture 工作流构建完成 (Workers: {len(workers)})")
    return compiled_graph


class GraphManager:
    """
    图管理器
    
    管理 LangGraph 工作流的生命周期，支持重建和重置。
    """
    
    def __init__(self):
        self._graph_app = None
        self._checkpointer: Optional[BaseCheckpointSaver] = None
        self._supervisor_config: Optional[SupervisorConfig] = None
    
    def get_app(
        self,
        checkpointer: Optional[BaseCheckpointSaver] = None,
        supervisor_config: Optional[SupervisorConfig] = None,
        force_rebuild: bool = False,
    ):
        """
        获取图应用实例
        
        Args:
            checkpointer: 可选的检查点存储器
            supervisor_config: 可选的 Supervisor 配置
            force_rebuild: 是否强制重建图
            
        Returns:
            编译后的 LangGraph 应用
        """
        # 检查是否需要重建
        should_rebuild = (
            force_rebuild or
            self._graph_app is None or
            (checkpointer is not None and checkpointer != self._checkpointer) or
            (supervisor_config is not None and supervisor_config != self._supervisor_config)
        )
        
        if should_rebuild:
            self._checkpointer = checkpointer
            self._supervisor_config = supervisor_config
            self._graph_app = build_graph(
                checkpointer=checkpointer,
                supervisor_config=supervisor_config,
            )
        
        return self._graph_app
    
    def reset(self) -> None:
        """重置图应用实例"""
        self._graph_app = None
        self._checkpointer = None
        self._supervisor_config = None
        logger.info("已重置图应用实例")
    
    def rebuild(self) -> None:
        """使用当前配置重建图"""
        self._graph_app = build_graph(
            checkpointer=self._checkpointer,
            supervisor_config=self._supervisor_config,
        )
        logger.info("已重建图应用实例")


# 全局图管理器实例
_graph_manager = GraphManager()


def get_graph_app(
    checkpointer: Optional[BaseCheckpointSaver] = None,
    supervisor_config: Optional[SupervisorConfig] = None,
):
    """
    获取全局图应用实例
    
    Args:
        checkpointer: 可选的检查点存储器
        supervisor_config: 可选的 Supervisor 配置
        
    Returns:
        编译后的 LangGraph 应用
    """
    return _graph_manager.get_app(
        checkpointer=checkpointer,
        supervisor_config=supervisor_config,
    )


def reset_graph_app() -> None:
    """重置全局图应用实例（用于测试或重新配置）"""
    _graph_manager.reset()


def rebuild_graph_app() -> None:
    """重建全局图应用实例（当 Worker 注册变化时调用）"""
    _graph_manager.rebuild()

