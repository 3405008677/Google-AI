# src/router/agents/workerAgents 目录

> 具体 Worker 实现：标准 Worker 与 Subgraph Worker。

---

## Worker 类型

| 类型 | 说明 | 示例 |
|:---|:---|:---|
| **Standard Worker** | 单步执行，可调用 Tools | General, Search |
| **Subgraph Worker** | 拥有自己的子工作流 | DataTeam |

---

## 文件结构

```
workerAgents/
├── __init__.py       # 导出
├── subgraphs.py      # 子图 Worker 实现
└── README.md
```

---

## DataTeam Worker（子图示例）

`DataTeamWorker` 是一个典型的 Subgraph Worker，内部包含完整的数据分析流程：

```
┌─────────────────────────────────────────────────────────────┐
│                      DataTeam Subgraph                       │
│                                                              │
│   ┌────────────┐    ┌────────────┐    ┌────────────┐        │
│   │SQL Generator│───▶│SQL Executor│───▶│Data Analyst│        │
│   │ (生成 SQL)  │    │ (执行 SQL) │    │ (分析结果) │        │
│   └────────────┘    └─────┬──────┘    └────────────┘        │
│                           │                                  │
│                      失败？─┼─ 成功                           │
│                        │   │                                 │
│                        ▼   │                                 │
│                   ┌────────┴───┐                             │
│                   │   Retry    │ ◀── 自愈：最多 3 次重试      │
│                   └────────────┘                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 子图状态

```python
class DataState(TypedDict):
    messages: List[BaseMessage]  # 消息历史
    question: str                # 原始问题
    sql_query: str               # 生成的 SQL
    query_result: str            # 执行结果
    error: Optional[str]         # 错误信息
    trials: int                  # 重试次数
    schema: str                  # 数据库 Schema
```

### 自愈机制

```
1. SQL Generator 生成 SQL
2. SQL Executor 执行
3. 如果执行失败：
   ├─ trials < 3 → 将错误信息返回给 Generator，重新生成
   └─ trials >= 3 → 放弃，返回错误信息
4. 如果执行成功：
   └─ Data Analyst 分析结果，生成报告
```

---

## 实现详解

### 1. 继承 SubgraphWorker

```python
from src.router.agents.supervisor.registry import SubgraphWorker

class DataTeamWorker(SubgraphWorker):
    def __init__(self):
        super().__init__(
            name="DataTeam",
            description="数据分析团队，负责数据库查询与分析",
            priority=15,
        )
    
    def build_subgraph(self):
        """构建子图工作流"""
        return build_data_subgraph()
    
    def prepare_subgraph_input(self, state) -> dict:
        """从父状态准备子图输入"""
        ...
    
    def process_subgraph_output(self, result, parent_state) -> dict:
        """处理子图输出，转换为父图格式"""
        ...
```

### 2. 子图节点

```python
# SQL Generator
def generate_sql_node(state: DataState) -> dict:
    """读取 Schema，生成 SQL"""
    ...

# SQL Executor
def execute_sql_node(state: DataState) -> dict:
    """执行 SQL，捕获错误"""
    ...

# Data Analyst
def analyze_result_node(state: DataState) -> dict:
    """分析结果，生成报告"""
    ...

# Give Up
def give_up_node(state: DataState) -> dict:
    """多次重试失败后，返回错误信息"""
    ...
```

### 3. 路由逻辑

```python
def check_execution(state: DataState) -> str:
    """决定下一步"""
    if state.get("error"):
        if state.get("trials", 0) >= 3:
            return "give_up"
        return "retry"
    return "success"
```

---

## 添加新 Worker

### Standard Worker

```python
from src.router.agents.supervisor.registry import BaseWorker

class MyWorker(BaseWorker):
    def __init__(self):
        super().__init__(
            name="MyWorker",
            description="我的 Worker 描述",
            priority=10,  # 越高越优先
        )
    
    async def run(self, state: SupervisorState) -> dict:
        # 获取当前任务
        task = self.get_current_task_step(state)
        
        # 执行逻辑
        result = await self._process(state)
        
        # 返回结果
        return {
            "messages": [AIMessage(content=result, name=self.name)],
            "current_worker": self.name,
        }
```

### Subgraph Worker

```python
from src.router.agents.supervisor.registry import SubgraphWorker

class MySubgraphWorker(SubgraphWorker):
    def __init__(self):
        super().__init__(
            name="MySubgraph",
            description="子图 Worker 描述",
            priority=15,
        )
    
    def build_subgraph(self):
        """构建 LangGraph StateGraph"""
        workflow = StateGraph(MyState)
        # 添加节点和边...
        return workflow.compile()
    
    def prepare_subgraph_input(self, state) -> dict:
        """准备子图输入"""
        return {"question": state.get("original_query")}
    
    def process_subgraph_output(self, result, parent_state) -> dict:
        """处理子图输出"""
        return {"messages": result.get("messages", [])}
```

---

## 注册 Worker

在 `supervisor/registry.py` 中注册：

```python
from src.router.agents.workerAgents.my_worker import MyWorker

# 注册
register_worker(MyWorker())

# 或在初始化时
def init_workers():
    register_worker(GeneralWorker())
    register_worker(SearchWorker())
    register_worker(DataTeamWorker())
    register_worker(MyWorker())  # 新增
```
