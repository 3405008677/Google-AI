"""
Supervisor Architecture

使用 LangGraph 实现的 Supervisor Architecture（主管模式）。
主管不直接干活，而是指挥手下的"专家团队"（Layer 4）去干活。

架构说明：
1. Supervisor: 主管节点，使用 LLM 进行任务规划和决策路由
2. Workers: 专家团队（Layer 4），执行具体任务
   - ResearcherWorker: 搜索与调研专家
   - DataAnalystWorker: 数据分析专家
   - DataTeamWorker: 数据分析团队（子图实现，支持自愈）
   - WriterWorker: 内容创作专家
   - GeneralWorker: 通用助手
3. State: 状态管理，维护对话历史、任务规划和用户上下文
4. Workflow: LangGraph 工作流，连接所有节点
5. Service: 服务层，提供 API 接口，集成 Performance Layer

使用示例：
    from src.router.agents.supervisor import (
        register_default_workers,
        get_service
    )
    
    # 注册默认 Worker
    register_default_workers()
    
    # 获取服务实例
    service = get_service()
    
    # 流式调用（支持 SSE）
    async for event in service.run_stream(
        "先搜一下竞品价格，再查我们的库存，最后写个分析报告",
        user_context={"user_id": "123", "language": "zh-CN"},
        sse_format=True  # 返回 SSE 格式字符串
    ):
        print(event)
    
    # 非流式调用
    result = await service.run("帮我研究一下 AI 的最新发展")
"""

# State
from src.router.agents.supervisor.state import (
    SupervisorState,
    DEFAULT_STATE,
    MAX_ITERATIONS,
    MAX_TASK_STEPS,
    TaskStatus,
    TaskStep,
    UserContext,
    ThinkingStep,
    DEFAULT_USER_CONTEXT,
    create_thinking_step,
    create_task_step,
)

# Registry
from src.router.agents.supervisor.registry import (
    Worker,
    WorkerType,
    WorkerRegistry,
    BaseWorkerMixin,
    SubgraphWorker,
    ToolWorker,
    get_registry,
    register_worker,
    get_worker,
)

# Workers
from src.router.agents.supervisor.worker import (
    ResearcherWorker,
    DataAnalystWorker,
    WriterWorker,
    GeneralWorker,
    WORKER_CLASSES,
    register_default_workers,
)

# Supervisor
from src.router.agents.supervisor.supervisor import (
    SupervisorConfig,
    RouteDecision,
    TaskPlan,
    create_supervisor_node,
)

# Workflow
from src.router.agents.supervisor.workflow import (
    GraphManager,
    build_graph,
    get_graph_app,
    reset_graph_app,
    rebuild_graph_app,
)

# Service
from src.router.agents.supervisor.service import (
    StreamEvent,
    StreamEventType,
    SupervisorService,
    get_service,
    reset_service,
)

__all__ = [
    # State
    "SupervisorState",
    "DEFAULT_STATE",
    "MAX_ITERATIONS",
    "MAX_TASK_STEPS",
    "TaskStatus",
    "TaskStep",
    "UserContext",
    "ThinkingStep",
    "DEFAULT_USER_CONTEXT",
    "create_thinking_step",
    "create_task_step",
    
    # Registry
    "Worker",
    "WorkerType",
    "WorkerRegistry",
    "BaseWorkerMixin",
    "SubgraphWorker",
    "ToolWorker",
    "get_registry",
    "register_worker",
    "get_worker",
    
    # Workers
    "ResearcherWorker",
    "DataAnalystWorker",
    "WriterWorker",
    "GeneralWorker",
    "WORKER_CLASSES",
    "register_default_workers",
    
    # Supervisor
    "SupervisorConfig",
    "RouteDecision",
    "TaskPlan",
    "create_supervisor_node",
    
    # Workflow
    "GraphManager",
    "build_graph",
    "get_graph_app",
    "reset_graph_app",
    "rebuild_graph_app",
    
    # Service
    "StreamEvent",
    "StreamEventType",
    "SupervisorService",
    "get_service",
    "reset_service",
]


def register_all_workers() -> None:
    """
    注册所有可用的 Worker（包括子图 Worker）
    
    这个函数注册：
    1. 默认的简单 Worker（Researcher, DataAnalyst, Writer, General）
    2. 子图 Worker（DataTeam）
    """
    # 注册默认 Worker
    register_default_workers()
    
    # 注册子图 Worker
    try:
        from src.router.agents.workerAgents.subgraphs import DataTeamWorker
        register_worker(DataTeamWorker())
    except Exception as e:
        from src.server.logging_setup import logger
        logger.warning(f"注册 DataTeamWorker 失败: {e}")
