# src/router/agents 目录

> Agent/Supervisor 核心架构：任务编排、Worker 调度、性能优化。

---

## 架构概览

```
                              用户请求
                                  │
                                  ▼
                         ┌───────────────┐
                         │    api.py     │
                         │  Agent API    │
                         └───────┬───────┘
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │   Performance Layer    │
                    │  ┌──────┐  ┌────────┐  │
                    │  │ Rule │  │Semantic│  │
                    │  │Engine│  │ Cache  │  │
                    │  └──────┘  └────────┘  │
                    └────────────┬───────────┘
                                 │
                        命中？ ──┼── 未命中
                          │      │
                          ▼      ▼
                       直接返回  继续
                                 │
                                 ▼
                    ┌────────────────────────┐
                    │      Supervisor        │
                    │   (LangGraph 工作流)    │
                    │                        │
                    │  1. 任务规划 (Planner)  │
                    │  2. Worker 调度        │
                    │  3. 结果聚合           │
                    └────────────┬───────────┘
                                 │
                 ┌───────────────┼───────────────┐
                 │               │               │
                 ▼               ▼               ▼
          ┌──────────┐    ┌──────────┐    ┌──────────┐
          │ General  │    │  Search  │    │ DataTeam │
          │  Worker  │    │  Worker  │    │(Subgraph)│
          └──────────┘    └──────────┘    └──────────┘
                 │               │               │
                 └───────────────┼───────────────┘
                                 │
                                 ▼
                         ┌───────────────┐
                         │ Tool Registry │
                         │  工具调用层    │
                         └───────────────┘
```

---

## 目录结构

```
agents/
├── __init__.py              # 导出注册函数
├── api.py                   # Agent API 端点
│
├── supervisor/              # Supervisor 核心
│   ├── service.py           # 服务入口
│   ├── workflow.py          # LangGraph 工作流
│   ├── state.py             # 状态定义
│   ├── registry.py          # Worker 注册表
│   ├── worker.py            # Worker 基类
│   └── llm_factory.py       # LLM 工厂
│
├── performance_layer/       # 性能优化层
│   └── index.py             # 规则引擎 + 语义缓存
│
├── workerAgents/            # 具体 Worker 实现
│   └── subgraphs.py         # 子图 Worker（如 DataTeam）
│
└── AI/                      # 模型适配层
    ├── Gemini/              # Google Gemini
    ├── Qwen/                # 通义千问
    └── Customize/           # 自定义模型
```

---

## API 端点 (api.py)

| 端点 | 方法 | 说明 |
|:---|:---|:---|
| `/agents/chat` | POST | 非流式对话 |
| `/agents/chat/stream` | POST | SSE 流式对话 |
| `/agents/chat/history/{thread_id}` | GET | 获取会话历史 |
| `/agents/workers` | GET | 列出可用 Worker |
| `/agents/workers/reset` | POST | 重置 Worker 状态 |

### 请求示例

```json
POST /agents/chat
{
  "message": "帮我分析一下最近的销售数据",
  "thread_id": "session-123",
  "model": "gemini",
  "stream": false
}
```

### SSE 流式响应

```
event: start
data: {"thread_id": "session-123"}

event: thinking
data: {"content": "正在分析您的请求..."}

event: tool_use
data: {"tool": "sql_query", "status": "executing"}

event: progress
data: {"step": 1, "total": 3, "description": "查询数据库"}

event: answer
data: {"content": "根据分析结果..."}

event: done
data: {"thread_id": "session-123", "tokens_used": 1234}
```

---

## 核心组件

### 1. Performance Layer（性能层）

在调用昂贵的 LLM 之前进行"速通"判断：

- **规则引擎**：匹配问候、帮助等简单意图。
- **语义缓存**：相似问题直接返回历史答案。

详细文档：[performance_layer/README.md](performance_layer/README.md)

### 2. Supervisor（监督者）

基于 LangGraph 的任务编排引擎：

- 接收用户请求，生成任务计划。
- 调度合适的 Worker 执行任务。
- 支持多步骤、多 Worker 协作。

详细文档：[supervisor/README.md](supervisor/README.md)

### 3. Workers（工作者）

执行具体任务的单元：

| Worker | 类型 | 职责 |
|:---|:---|:---|
| General | Standard | 通用问答、日常对话 |
| Search | Standard | 联网搜索、信息检索 |
| DataTeam | Subgraph | 数据库查询与分析 |

详细文档：[workerAgents/README.md](workerAgents/README.md)

### 4. AI 适配层

统一的模型接入层，支持多种模型提供方：

- Gemini (Google)
- Qwen (阿里云)
- Customize (OpenAI 兼容接口)

详细文档：[AI/README.md](AI/README.md)

---

## 数据流

```
1. 用户请求 → api.py
2. → Performance Layer 检查
   ├─ 命中规则/缓存 → 直接返回
   └─ 未命中 → 继续
3. → SupervisorService.process()
4. → LangGraph Workflow 执行
5. → Worker(s) 处理
6. → 工具调用（如需要）
7. → 结果聚合
8. → 响应用户
```

---

## 子目录文档

| 目录 | 说明 |
|:---|:---|
| [supervisor/](supervisor/README.md) | Supervisor 核心实现 |
| [performance_layer/](performance_layer/README.md) | 性能优化层 |
| [workerAgents/](workerAgents/README.md) | Worker 实现 |
| [AI/](AI/README.md) | 模型适配层 |
