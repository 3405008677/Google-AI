# src/router/agents/supervisor 目录

> Supervisor 架构核心：任务拆解、Worker 调度、工作流执行。

---

## 架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                        SupervisorService                         │
│                         (service.py)                             │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      LangGraph Workflow                          │
│                        (workflow.py)                             │
│                                                                  │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│   │  Start   │───▶│ Planner  │───▶│ Router   │───▶│Aggregator│  │
│   └──────────┘    └──────────┘    └────┬─────┘    └──────────┘  │
│                                        │                         │
│                        ┌───────────────┼───────────────┐         │
│                        │               │               │         │
│                        ▼               ▼               ▼         │
│                   ┌────────┐      ┌────────┐      ┌────────┐    │
│                   │Worker A│      │Worker B│      │Worker C│    │
│                   └────────┘      └────────┘      └────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │    SupervisorState    │
                    │      (state.py)       │
                    └───────────────────────┘
```

---

## 文件结构

```
supervisor/
├── __init__.py        # 导出
├── service.py         # 服务入口（流式/非流式）
├── workflow.py        # LangGraph 工作流构建
├── state.py           # 状态定义（TypedDict）
├── registry.py        # Worker 注册表
├── worker.py          # Worker 基类与执行
└── llm_factory.py     # LLM 创建工厂
```

---

## 核心组件

### 1. SupervisorService (service.py)

对外的统一服务入口：

```python
class SupervisorService:
    async def process(
        self,
        message: str,
        thread_id: str,
        user_context: dict = None,
    ) -> str:
        """非流式处理"""
        ...
    
    async def process_stream(
        self,
        message: str,
        thread_id: str,
        user_context: dict = None,
    ) -> AsyncGenerator[dict, None]:
        """SSE 流式处理"""
        ...
```

### 2. SupervisorState (state.py)

LangGraph 状态结构：

```python
class SupervisorState(TypedDict):
    messages: List[BaseMessage]      # 对话历史
    task_plan: List[TaskStep]        # 任务计划
    current_step_index: int          # 当前步骤
    current_worker: str              # 当前 Worker
    original_query: str              # 原始问题
    user_context: dict               # 用户上下文（模型配置等）
    final_response: str              # 最终响应
```

### 3. TaskStep（任务步骤）

```python
class TaskStep(TypedDict):
    step_id: str                     # 步骤 ID
    description: str                 # 步骤描述
    worker: str                      # 执行 Worker
    status: TaskStatus               # pending/in_progress/completed/failed
    result: Optional[str]            # 执行结果
    error: Optional[str]             # 错误信息
```

### 4. Worker Registry (registry.py)

Worker 注册与发现：

```python
from src.router.agents.supervisor.registry import (
    register_worker,
    get_worker,
    list_workers,
)

# 注册 Worker
register_worker(GeneralWorker())

# 获取 Worker
worker = get_worker("General")

# 列出所有 Worker
workers = list_workers()
```

---

## 工作流节点

### Planner（规划节点）

分析用户请求，生成任务计划：

```python
def planner_node(state: SupervisorState) -> dict:
    """
    输入：用户消息
    输出：task_plan（任务步骤列表）
    """
    ...
```

### Router（路由节点）

根据当前步骤选择 Worker：

```python
def router_node(state: SupervisorState) -> str:
    """
    输入：task_plan, current_step_index
    输出：下一个节点名（Worker 名或 "aggregate"）
    """
    ...
```

### Worker Node（工作节点）

执行具体任务：

```python
def create_worker_node(worker: BaseWorker):
    async def node(state: SupervisorState) -> dict:
        result = await worker.run(state)
        return result
    return node
```

### Aggregator（聚合节点）

汇总所有步骤结果，生成最终响应：

```python
def aggregator_node(state: SupervisorState) -> dict:
    """
    输入：所有步骤的 result
    输出：final_response
    """
    ...
```

---

## LLM Factory (llm_factory.py)

统一的模型创建入口：

```python
from src.router.agents.supervisor.llm_factory import create_llm_from_context

# 根据 user_context 创建 LLM
llm = create_llm_from_context(
    user_context={"model": "gemini"},
    temperature=0.7,
)

# 模型优先级：Customize > Qwen > Gemini
```

---

## 典型调用链

```
api.py
  │
  ├─ Depends(get_supervisor_service)
  │
  ▼
SupervisorService.process()
  │
  ├─ 构建初始 State
  │
  ▼
workflow.invoke(state)
  │
  ├─ planner_node → 生成任务计划
  │
  ├─ router_node → 选择 Worker
  │     │
  │     ├─ worker_node (General)
  │     │
  │     ├─ worker_node (Search)
  │     │
  │     └─ ... (循环直到所有步骤完成)
  │
  ├─ aggregator_node → 聚合结果
  │
  ▼
返回 final_response
```

---

## 扩展：添加新 Worker

### 1. 创建 Worker 类

```python
# src/router/agents/workerAgents/my_worker.py

from src.router.agents.supervisor.registry import BaseWorker

class MyWorker(BaseWorker):
    def __init__(self):
        super().__init__(
            name="MyWorker",
            description="我的自定义 Worker",
            priority=10,
        )
    
    async def run(self, state: SupervisorState) -> dict:
        # 执行逻辑
        result = await self._process(state)
        return {"messages": [AIMessage(content=result)]}
```

### 2. 注册 Worker

```python
# src/router/agents/supervisor/registry.py

from src.router.agents.workerAgents.my_worker import MyWorker

register_worker(MyWorker())
```
