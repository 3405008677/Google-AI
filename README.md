# Google-AI Project

> **企业级 AI 服务工程化解决方案**
>
> 基于 LangGraph Supervisor/Worker 架构，集成语义缓存、规则引擎、Function Calling 工具体系，以及完整的生产级服务治理能力。

---

## 目录

- [1. 项目定位](#1-项目定位)
- [2. 为什么选择这个架构](#2-为什么选择这个架构)
- [3. 架构深度解析](#3-架构深度解析)
- [4. 完整请求流程](#4-完整请求流程)
- [5. 与其他架构的对比](#5-与其他架构的对比)
- [6. 核心模块详解](#6-核心模块详解)
- [7. 快速开始](#7-快速开始)
- [8. 配置详解](#8-配置详解)
- [9. 开发指南](#9-开发指南)
- [10. 生产环境建议](#10-生产环境建议)

---

## 1. 项目定位

### 1.1 解决什么问题？

在将 LLM 能力服务化的过程中，开发者常面临以下挑战：

| 痛点 | 具体表现 | 本项目解决方案 |
|:---|:---|:---|
| **复杂任务难以编排** | 单一 Prompt 无法处理"先搜索、再分析、最后生成报告"等多步骤任务 | LangGraph Supervisor/Worker 架构，自动拆解任务 |
| **成本与延迟失控** | 简单问候、重复问题也调用 LLM，成本高、响应慢 | Performance Layer（规则引擎 + 语义缓存）实现"0 Token"速通 |
| **服务治理缺失** | 无认证、无限流、无追踪，难以进入生产环境 | 完整中间件链：JWT 认证、滑动窗口限流、链路追踪 |
| **模型切换成本高** | 不同供应商接口不一致，切换需要改代码 | 统一 LLM Factory，配置即切换 |
| **工具管理混乱** | Function Calling 定义散落各处，难以维护 | YAML 驱动的 Tool Registry，集中管理 |

### 1.2 适用场景

- ✅ 构建企业内部 AI 中台服务
- ✅ 需要多步骤任务编排的智能助手
- ✅ 对成本敏感、需要缓存优化的高频问答场景
- ✅ 需要完整服务治理的生产级部署
- ✅ 需要支持多种 LLM（Gemini/Qwen/私有化部署）的项目

---

## 2. 为什么选择这个架构

### 2.1 架构选型理念

```
                    传统架构                          本项目架构
                    
    用户 ──→ LLM ──→ 响应               用户 ──→ 性能层 ──→ Supervisor ──→ Workers ──→ Tools
                                              ↓                    ↓
                                          规则/缓存命中         任务拆解+调度
                                              ↓                    ↓
                                          直接返回              多步骤执行
```

#### 核心设计原则

1. **"能不调 LLM 就不调"原则**
   - 规则引擎处理问候、帮助等固定意图（< 1ms）
   - 语义缓存处理相似问题（< 10ms）
   - 只有真正需要推理的请求才进入 LLM

2. **"分而治之"原则**
   - 复杂任务由 Supervisor 拆解为多个步骤
   - 每个步骤由专门的 Worker 执行
   - Worker 可以是单步执行，也可以是嵌套子图

3. **"动态路由"原则**
   - 根据任务类型自动选择合适的 Worker
   - 支持运行时动态注册新 Worker
   - 失败时自动重试或切换策略

### 2.2 为什么选择 LangGraph？

| 对比维度 | 传统 Chain | ReAct Agent | **LangGraph Supervisor** |
|:---|:---|:---|:---|
| 任务拆解 | ❌ 不支持 | ⚠️ 隐式（依赖 LLM） | ✅ 显式规划（Task Plan） |
| 流程控制 | 线性 | 循环 | **图结构（任意拓扑）** |
| 可观测性 | 差 | 一般 | **优秀（节点级追踪）** |
| 错误恢复 | 需手动 | 部分 | **内置自愈机制** |
| 可扩展性 | 低 | 中 | **高（热插拔 Worker）** |
| 嵌套能力 | ❌ | ❌ | ✅ 支持子图（Subgraph） |

### 2.3 技术选型总结

| 技术 | 选型 | 理由 |
|:---|:---|:---|
| Web 框架 | **FastAPI** | 异步原生、类型安全、自动文档 |
| 编排引擎 | **LangGraph** | 图结构、状态管理、检查点支持 |
| 缓存 | **Redis + sentence-transformers** | 成熟稳定、向量相似度检索 |
| 认证 | **JWT** | 无状态、易扩展、标准协议 |
| 配置 | **dataclass + dotenv** | 类型安全、IDE 友好 |

---

## 3. 架构深度解析

### 3.1 系统架构全景图

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                                    Client                                         │
│                              (HTTP / SSE / WebSocket)                             │
└────────────────────────────────────────┬─────────────────────────────────────────┘
                                         │
                                         ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              Router Layer (治理层)                                │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│  │   Tracing   │───▶│    Auth     │───▶│ Rate Limit  │───▶│   Health    │        │
│  │ (链路追踪)  │    │  (JWT认证)   │    │  (滑动窗口)  │    │  (探针/指标) │        │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘        │
└────────────────────────────────────────┬─────────────────────────────────────────┘
                                         │
                                         ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                           Performance Layer (性能层)                              │
│                                                                                   │
│    ┌─────────────────┐              ┌─────────────────────────────────────┐      │
│    │   Rule Engine   │   命中 ────▶ │         直接返回（< 1ms）            │      │
│    │   (规则引擎)     │              └─────────────────────────────────────┘      │
│    └────────┬────────┘                                                           │
│             │ 未命中                                                              │
│             ▼                                                                     │
│    ┌─────────────────┐              ┌─────────────────────────────────────┐      │
│    │ Semantic Cache  │   命中 ────▶ │      返回缓存答案（< 10ms）           │      │
│    │   (语义缓存)     │              └─────────────────────────────────────┘      │
│    └────────┬────────┘                                                           │
│             │ 未命中                                                              │
└─────────────┼────────────────────────────────────────────────────────────────────┘
              │
              ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                            Agent Core (编排层)                                    │
│                                                                                   │
│    ┌─────────────────────────────────────────────────────────────────────────┐   │
│    │                         SupervisorService                                │   │
│    │                                                                          │   │
│    │   ┌───────────────────────────────────────────────────────────────┐     │   │
│    │   │                   LangGraph Workflow                           │     │   │
│    │   │                                                                │     │   │
│    │   │     ┌────────────┐         ┌────────────┐                      │     │   │
│    │   │     │ Supervisor │◀───────▶│  Planner   │                      │     │   │
│    │   │     │  (决策中枢) │         │ (任务规划)  │                      │     │   │
│    │   │     └─────┬──────┘         └────────────┘                      │     │   │
│    │   │           │                                                    │     │   │
│    │   │           │ 路由决策                                            │     │   │
│    │   │           ▼                                                    │     │   │
│    │   │     ┌─────────────────────────────────────────────────┐        │     │   │
│    │   │     │              Worker Registry                     │        │     │   │
│    │   │     │                                                  │        │     │   │
│    │   │     │  ┌─────────┐  ┌─────────┐  ┌──────────────────┐ │        │     │   │
│    │   │     │  │ General │  │ Search  │  │    DataTeam      │ │        │     │   │
│    │   │     │  │ Worker  │  │ Worker  │  │   (Subgraph)     │ │        │     │   │
│    │   │     │  │         │  │         │  │                  │ │        │     │   │
│    │   │     │  │ 通用问答 │  │ 联网搜索 │  │ ┌──────────────┐ │ │        │     │   │
│    │   │     │  │         │  │         │  │ │ SQL Generator│ │ │        │     │   │
│    │   │     │  │         │  │         │  │ │      ↓       │ │ │        │     │   │
│    │   │     │  │         │  │         │  │ │ SQL Executor │ │ │        │     │   │
│    │   │     │  │         │  │         │  │ │      ↓       │ │ │        │     │   │
│    │   │     │  │         │  │         │  │ │ Data Analyst │ │ │        │     │   │
│    │   │     │  │         │  │         │  │ └──────────────┘ │ │        │     │   │
│    │   │     │  └─────────┘  └─────────┘  └──────────────────┘ │        │     │   │
│    │   │     └─────────────────────────────────────────────────┘        │     │   │
│    │   └────────────────────────────────────────────────────────────────┘     │   │
│    └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                   │
└────────────────────────────────────────┬─────────────────────────────────────────┘
                                         │
                                         ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              Tool Layer (工具层)                                  │
│                                                                                   │
│    ┌─────────────────────────────────────────────────────────────────────────┐   │
│    │                          Tool Registry                                   │   │
│    │                                                                          │   │
│    │   ┌───────────────┐  ┌───────────────┐  ┌───────────────┐               │   │
│    │   │ get_datetime  │  │  web_search   │  │  custom_tool  │  ...          │   │
│    │   └───────────────┘  └───────────────┘  └───────────────┘               │   │
│    │                                                                          │   │
│    │   - YAML Schema 定义                                                     │   │
│    │   - 按 Worker 分配权限                                                    │   │
│    │   - 同步/异步执行器                                                       │   │
│    └──────────────────────────────────────────────────────────────────────────┘   │
│                                                                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 分层职责

| 层级 | 职责 | 核心组件 | 位置 |
|:---|:---|:---|:---|
| **Router Layer** | 请求接入、安全防护、可观测性 | Tracing, Auth, RateLimit, Health | `src/router/` |
| **Performance Layer** | 成本优化、延迟优化 | RuleEngine, SemanticCache | `src/router/agents/performance_layer/` |
| **Agent Core** | 任务编排、决策路由 | Supervisor, Workers, Workflow | `src/router/agents/supervisor/` |
| **Tool Layer** | 能力扩展、外部集成 | ToolRegistry, Executors | `src/common/function_calls/` |

---

## 4. 完整请求流程

### 4.1 请求处理时序图

```
┌──────┐     ┌───────┐     ┌─────────┐     ┌─────────────┐     ┌──────────┐     ┌────────┐
│Client│     │Tracing│     │  Auth   │     │ Performance │     │Supervisor│     │ Worker │
└──┬───┘     └───┬───┘     └────┬────┘     │   Layer     │     └────┬─────┘     └───┬────┘
   │             │              │          └──────┬──────┘          │               │
   │  POST /chat │              │                 │                 │               │
   │────────────▶│              │                 │                 │               │
   │             │              │                 │                 │               │
   │             │ 生成 TraceID │                 │                 │               │
   │             │──────────────▶                 │                 │               │
   │             │              │                 │                 │               │
   │             │              │ 验证 JWT Token  │                 │               │
   │             │              │─────────────────▶                 │               │
   │             │              │                 │                 │               │
   │             │              │                 │ 1. 规则引擎检查  │               │
   │             │              │                 │◀────────────────│               │
   │             │              │                 │                 │               │
   │             │              │                 │ 2. 语义缓存检查  │               │
   │             │              │                 │◀────────────────│               │
   │             │              │                 │                 │               │
   │             │              │                 │    [未命中]     │               │
   │             │              │                 │─────────────────▶               │
   │             │              │                 │                 │               │
   │             │              │                 │                 │ 3. 任务规划   │
   │             │              │                 │                 │──────────────▶│
   │             │              │                 │                 │               │
   │             │              │                 │                 │ 4. 执行任务   │
   │             │              │                 │                 │◀──────────────│
   │             │              │                 │                 │               │
   │             │              │                 │                 │ 5. 汇报结果   │
   │             │              │                 │                 │──────────────▶│
   │             │              │                 │                 │               │
   │             │              │                 │ 6. 缓存答案     │               │
   │             │              │                 │◀────────────────│               │
   │             │              │                 │                 │               │
   │◀────────────────────────────────────────────────────────────────               │
   │                      响应 + TraceID + 耗时                                      │
```

### 4.2 详细处理步骤

#### Step 1: 路由治理层

```python
# 1.1 Tracing 中间件
# - 从 X-Trace-ID / X-Request-ID 读取或自动生成 TraceID
# - 注入日志上下文，便于全链路追踪
# - 响应时返回 X-Trace-ID 和 X-Router-Process-Time

# 1.2 Auth 中间件
# - 检查 Authorization: Bearer <token>
# - 验证 JWT 签名和有效期
# - 将用户信息写入 request.state

# 1.3 RateLimit 中间件
# - 基于 IP 的滑动窗口计数
# - 默认 100 请求/分钟
# - 超限返回 429 Too Many Requests
```

#### Step 2: 性能优化层

```python
# 2.1 规则引擎检查（< 1ms）
rule_result = rule_engine.match(query)
if rule_result:
    return {"answer": rule_result["answer"], "source": "rule_engine"}

# 2.2 语义缓存检查（< 10ms）
# - 将 Query 向量化（sentence-transformers）
# - 在 Redis 中搜索相似向量
# - 相似度 > 0.95 则返回缓存答案
cache_result = semantic_cache.get(query)
if cache_result:
    return {"answer": cache_result["answer"], "source": "cache"}
```

#### Step 3: Supervisor 任务规划

```python
# 3.1 任务分析
# Supervisor 分析用户请求，判断复杂度

# 3.2 生成任务计划（Task Plan）
task_plan = [
    {"step_id": "step_1", "worker": "Search", "description": "搜索相关信息"},
    {"step_id": "step_2", "worker": "General", "description": "整理并回答"},
]

# 3.3 路由决策
# - 单步简单任务：直接路由到 General
# - 多步复杂任务：按计划顺序调度
```

#### Step 4: Worker 执行

```python
# 4.1 Standard Worker（单步执行）
class GeneralWorker(BaseWorker):
    async def run(self, state):
        # 调用 LLM 处理任务
        response = await llm.ainvoke(messages)
        return {"messages": [AIMessage(content=response)]}

# 4.2 Subgraph Worker（子图执行）
class DataTeamWorker(SubgraphWorker):
    def build_subgraph(self):
        # 内部包含 SQL生成 → 执行 → 分析 的完整流程
        # 支持自动重试（最多 3 次）
```

#### Step 5: 结果缓存与返回

```python
# 5.1 缓存答案
semantic_cache.set(query, final_answer)

# 5.2 返回响应
# - 非流式：直接返回 JSON
# - 流式：SSE 实时推送
```

### 4.3 SSE 流式事件

```
event: start
data: {"type": "start"}

event: progress
data: {"type": "progress", "progress": {"current": 1, "total": 2}}

event: answer
data: {"type": "answer", "content": "根据搜索结果..."}

event: done
data: {"type": "done"}
```

---

## 5. 与其他架构的对比

### 5.1 常见 LLM 应用架构

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              架构演进路线                                        │
│                                                                                  │
│   Level 1          Level 2          Level 3          Level 4 (本项目)            │
│   ────────         ────────         ────────         ──────────────────          │
│                                                                                  │
│   直接调用          Chain 链式        ReAct Agent      Supervisor/Worker          │
│                                                                                  │
│   User             User             User             User                        │
│     │                │                │                │                         │
│     ▼                ▼                ▼                ▼                         │
│    LLM          Prompt→LLM→       ┌──────┐        ┌──────────┐                  │
│     │           Parse→Tool        │ LLM  │◀──┐    │Supervisor│                  │
│     ▼                │            └──┬───┘   │    └────┬─────┘                  │
│   Output            ▼               │       │         │                         │
│                  Output          Observe    │    ┌────┴────┐                    │
│                                     │       │    ▼         ▼                    │
│                                     ▼       │  Worker   Worker                  │
│                                   Action────┘    │         │                    │
│                                                  ▼         ▼                    │
│                                               Tools     Tools                   │
│                                                                                  │
│   优点：简单        优点：可组合      优点：自主决策    优点：                      │
│   缺点：能力单一    缺点：线性流程    缺点：不可控       - 可控的任务拆解             │
│                    缺点：无状态                         - 专业化 Worker              │
│                                                        - 显式状态管理               │
│                                                        - 支持嵌套子图               │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 详细对比

| 维度 | 直接调用 | LangChain | ReAct Agent | **本项目架构** |
|:---|:---|:---|:---|:---|
| **任务拆解** | ❌ 不支持 | ⚠️ 手动编排 | ⚠️ 隐式（LLM 决定） | ✅ 显式规划（Task Plan） |
| **流程可控性** | 高 | 高 | 低 | **高（图结构 + 快速路径）** |
| **成本优化** | ❌ | ❌ | ❌ | ✅ 规则引擎 + 语义缓存 |
| **错误恢复** | 需手动 | 需手动 | 部分 | ✅ 自动重试 + 降级 |
| **可观测性** | 差 | 一般 | 一般 | ✅ 节点级追踪 |
| **扩展性** | 低 | 中 | 中 | ✅ 热插拔 Worker |
| **嵌套能力** | ❌ | ❌ | ❌ | ✅ Subgraph Worker |
| **服务治理** | 需自建 | 需自建 | 需自建 | ✅ 内置完整方案 |

### 5.3 本项目的核心优势

#### 1. 三层防御降低成本

```
请求 ──→ 规则引擎（问候/帮助等）──→ 语义缓存（相似问题）──→ LLM（真正推理）
           │                          │                      │
           ▼                          ▼                      ▼
         < 1ms                      < 10ms               100ms ~ 10s
         0 Token                    0 Token              正常消耗
```

#### 2. 显式任务规划

```python
# ReAct Agent（不可控）
# LLM 自己决定下一步，可能陷入循环或遗漏步骤

# 本项目（可控）
task_plan = [
    {"worker": "Search", "description": "搜索信息"},      # 步骤明确
    {"worker": "General", "description": "整理回答"},     # 顺序清晰
]
# Supervisor 按计划执行，同时保留 LLM 智能路由的灵活性
```

#### 3. 快速路径优化

```python
# 传统方式：每次决策都调用 LLM
# 本项目：多级快速路径

# 快速路径 1：所有步骤完成 → 直接结束
if completed_steps >= total_steps:
    return "FINISH"

# 快速路径 2：单步任务已有回复 → 直接结束
if total_steps == 1 and has_ai_response:
    return "FINISH"

# 快速路径 3：按计划顺序执行 → 不调用 LLM
for step in task_plan:
    if step.status == PENDING:
        return step.worker

# 只有复杂情况才调用 LLM 决策
```

#### 4. Subgraph 嵌套能力

```
                    DataTeam Worker
                          │
            ┌─────────────┼─────────────┐
            │             │             │
            ▼             ▼             ▼
      SQL Generator  SQL Executor  Data Analyst
            │             │             │
            └──────┬──────┘             │
                   │ 失败重试            │
                   └────────────────────┘
                        自愈闭环
```

---

## 6. 核心模块详解

### 6.1 Performance Layer（性能层）

#### 规则引擎

```python
# 内置规则示例
RULES = [
    (r"^(你好|hello|hi).*$", "你好！有什么可以帮助你的？", "greeting"),
    (r"^(帮助|help).*$", "我可以帮助你回答问题...", "help"),
    (r"^(清除.*历史).*$", "已清除对话历史", "clear_history"),
]

# 匹配逻辑
for pattern, answer, rule_type in rules:
    if re.match(pattern, query, re.IGNORECASE):
        return {"answer": answer, "source": "rule_engine"}
```

#### 语义缓存

```python
# 核心流程
1. query → sentence-transformers → 向量 (384维)
2. 在 Redis 中搜索相似向量
3. 计算余弦相似度
4. 相似度 > 0.95 → 返回缓存答案
5. 否则 → 调用 LLM → 缓存结果
```

### 6.2 Supervisor（监督者）

#### 职责

1. **任务规划**：分析请求，生成 Task Plan
2. **路由决策**：决定下一步由哪个 Worker 执行
3. **进度追踪**：监控任务执行状态
4. **异常处理**：失败时重试或降级

#### 快速路径优化

```python
# Supervisor 的决策逻辑优先使用快速路径，减少 LLM 调用

async def _route_decision(state):
    # 快速路径 1：所有步骤完成
    if completed_steps >= total_steps:
        return {"next": "FINISH"}
    
    # 快速路径 2：单步任务已回复
    if total_steps == 1 and has_ai_response:
        return {"next": "FINISH"}
    
    # 快速路径 3：按计划顺序执行
    for step in task_plan:
        if step.status == PENDING:
            return {"next": step.worker}
    
    # 复杂情况：调用 LLM 决策
    return await llm_route_decision(state)
```

### 6.3 Worker（工作者）

#### 类型

| 类型 | 特点 | 示例 |
|:---|:---|:---|
| **Standard Worker** | 单步执行，可调用 Tools | General, Search |
| **Subgraph Worker** | 拥有子工作流，支持自愈 | DataTeam |

#### Worker 生命周期

```
                    Supervisor
                        │
                        │ 分配任务
                        ▼
┌───────────────────────────────────────────────────┐
│                     Worker                         │
│                                                    │
│   1. prepare_input()   - 准备输入                  │
│         │                                          │
│         ▼                                          │
│   2. execute()         - 执行任务（调用 LLM/Tools） │
│         │                                          │
│         ▼                                          │
│   3. process_output()  - 处理输出                  │
│         │                                          │
│         ▼                                          │
│   4. 返回结果给 Supervisor                         │
│                                                    │
└───────────────────────────────────────────────────┘
```

### 6.4 Tool Registry（工具注册中心）

#### YAML 驱动

```yaml
# src/common/function_calls/config.yaml

tools:
  get_current_time:
    description: "获取当前日期时间"
    parameters:
      type: object
      properties:
        timezone:
          type: string
          description: "时区"
      required: []

  web_search:
    description: "搜索互联网"
    parameters:
      type: object
      properties:
        query:
          type: string
      required: ["query"]

# Worker 权限分配
worker_tools:
  General:
    - get_current_time
  Search:
    - web_search
    - get_current_time
```

---

## 7. 快速开始

### 7.1 环境要求

- Python >= 3.10
- (可选) Redis >= 6.0（用于语义缓存）

### 7.2 安装

```bash
# 克隆项目
git clone https://github.com/your-repo/google-ai.git
cd google-ai

# 创建虚拟环境
python -m venv .venv

# Windows
.\.venv\Scripts\Activate.ps1
# Linux/Mac
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 7.3 配置

```bash
# 复制配置文件
cp env.example .env

# 编辑 .env，至少配置一个模型
```

```ini
# .env 最小配置

# 模型（三选一）
GEMINI_API_KEY=your_key          # Google Gemini
# QWEN_API_KEY=your_key          # 通义千问
# SELF_MODEL_BASE_URL=http://... # 自定义模型

# 安全（生产环境必改）
JWT_SECRET_KEY=your_secure_random_string
```

### 7.4 启动

```bash
python -m src.main
```

服务启动后：
- API 地址：`http://127.0.0.1:8080`
- 健康检查：`GET /health`
- API 文档：`GET /docs`（DEBUG 模式）

### 7.5 测试调用

```bash
# 登录获取 Token
curl -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'

# 对话测试
curl -X POST http://localhost:8080/agents/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"message": "你好"}'
```

---

## 8. 配置详解

### 8.1 服务器配置

| 变量 | 说明 | 默认值 |
|:---|:---|:---|
| `HOST` | 监听地址 | `0.0.0.0` |
| `PORT` | 监听端口 | `8080` |
| `WORKERS` | Uvicorn 进程数 | `1` |
| `DEBUG` | 调试模式 | `false` |
| `LOG_LEVEL` | 日志级别 | `INFO` |

### 8.2 模型配置

| 模型 | 变量 | 说明 |
|:---|:---|:---|
| **Gemini** | `GEMINI_API_KEY` | API 密钥 |
| | `GEMINI_MODEL` | 模型名（默认 `gemini-1.5-flash`） |
| **Qwen** | `QWEN_API_KEY` | DashScope API 密钥 |
| | `QWEN_MODEL` | 模型名（默认 `qwen-plus`） |
| **自定义** | `SELF_MODEL_BASE_URL` | OpenAI 兼容接口地址 |
| | `SELF_MODEL_NAME` | 模型名 |

### 8.3 性能层配置

| 变量 | 说明 | 默认值 |
|:---|:---|:---|
| `ENABLE_RULE_ENGINE` | 启用规则引擎 | `true` |
| `ENABLE_SEMANTIC_CACHE` | 启用语义缓存 | `true` |
| `SEMANTIC_CACHE_THRESHOLD` | 缓存相似度阈值 | `0.95` |
| `REDIS_HOST` | Redis 地址 | `localhost` |
| `REDIS_PORT` | Redis 端口 | `6379` |

### 8.4 安全配置

| 变量 | 说明 | 默认值 |
|:---|:---|:---|
| `JWT_SECRET_KEY` | JWT 签名密钥 | `secret`（必改） |
| `JWT_ALGORITHM` | 签名算法 | `HS256` |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Access Token 有效期 | `30` |
| `AUTH_ADMIN_USERNAME` | 管理员用户名 | `admin` |
| `AUTH_ADMIN_PASSWORD` | 管理员密码 | `admin`（必改） |

---

## 9. 开发指南

### 9.1 添加新 Worker

```python
# src/router/agents/workerAgents/my_worker.py

from src.router.agents.supervisor.registry import BaseWorker

class MyWorker(BaseWorker):
    def __init__(self):
        super().__init__(
            name="MyWorker",
            description="我的自定义 Worker，擅长处理 XXX 任务",
            priority=10,
        )
    
    async def run(self, state):
        # 1. 获取当前任务
        task = self.get_current_task_step(state)
        
        # 2. 处理任务
        result = await self._process(state)
        
        # 3. 返回结果
        return {
            "messages": [AIMessage(content=result, name=self.name)],
        }
```

### 9.2 添加新工具

```yaml
# src/common/function_calls/config.yaml

tools:
  my_tool:
    description: "工具描述"
    parameters:
      type: object
      properties:
        param1:
          type: string
          description: "参数说明"
      required: ["param1"]
```

```python
# src/tools/my_tool.py

def invoke(param1: str) -> str:
    return f"结果: {param1}"

async def ainvoke(param1: str) -> str:
    return invoke(param1)
```

### 9.3 自定义规则

```python
# 在 PerformanceLayer 初始化后添加

performance_layer.rule_engine.add_rule(
    pattern=r"^查询.*订单.*$",
    answer="请提供订单号，我来帮您查询。",
    rule_type="order_query",
)
```

---

## 10. 生产环境建议

### 10.1 安全加固

```bash
# 1. 生成安全的 JWT 密钥
python -c "import secrets; print(secrets.token_urlsafe(32))"

# 2. 修改默认密码
AUTH_ADMIN_PASSWORD=<strong_password>

# 3. 启用 HTTPS
SSL_ENABLED=true
SERVER_SSL_CERTFILE=/path/to/cert.pem
SERVER_SSL_KEYFILE=/path/to/key.pem
```

### 10.2 性能优化

```bash
# 1. 启用语义缓存（需要 Redis）
ENABLE_SEMANTIC_CACHE=true
REDIS_HOST=your-redis-host

# 2. 调整缓存阈值（0.9~0.98）
SEMANTIC_CACHE_THRESHOLD=0.95

# 3. 多进程部署
WORKERS=4
```

### 10.3 可观测性

```bash
# 1. 启用结构化日志
LOG_FORMAT=json

# 2. 接入监控
# - /health 用于存活探针
# - /ready 用于就绪探针
# - /metrics 用于 Prometheus 抓取

# 3. 保留 TraceID
# 所有日志自动关联 TraceID，便于链路追踪
```

### 10.4 部署架构建议

```
                    ┌─────────────┐
                    │   Nginx     │
                    │  (SSL/LB)   │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
    ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
    │  Instance 1 │ │  Instance 2 │ │  Instance 3 │
    │   (8080)    │ │   (8081)    │ │   (8082)    │
    └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
           │               │               │
           └───────────────┼───────────────┘
                           │
                    ┌──────▼──────┐
                    │    Redis    │
                    │  (缓存/限流) │
                    └─────────────┘
```

---

## 11. 目录结构

```
src/
├── main.py                 # 启动入口
├── config.py               # 应用配置
│
├── server/                 # FastAPI 应用组装
│   ├── app.py              # 创建 FastAPI 实例
│   ├── server.py           # Uvicorn 启动封装
│   └── ...
│
├── router/                 # 路由系统
│   ├── index.py            # 路由初始化入口
│   ├── health.py           # 健康检查端点
│   │
│   ├── agents/             # Agent 核心
│   │   ├── api.py          # Agent API
│   │   ├── supervisor/     # Supervisor 实现
│   │   ├── performance_layer/  # 性能优化层
│   │   ├── workerAgents/   # Worker 实现
│   │   └── AI/             # 模型适配层
│   │
│   ├── services/           # 业务服务
│   │   └── authorization/  # JWT 授权
│   │
│   └── utils/              # 路由工具
│       └── middlewares/    # 中间件
│
├── core/                   # 核心基础设施
│   ├── settings.py         # 配置中心
│   └── dependencies.py     # 依赖注入
│
├── common/                 # 通用能力
│   ├── prompts/            # 提示词管理
│   └── function_calls/     # 工具注册
│
└── tools/                  # 工具实现
    ├── datetime_tool.py
    └── search.py
```

---

## 12. 进一步阅读

| 模块 | 文档 |
|:---|:---|
| 源码总览 | [src/README.md](src/README.md) |
| 路由系统 | [src/router/README.md](src/router/README.md) |
| Agent 架构 | [src/router/agents/README.md](src/router/agents/README.md) |
| Supervisor | [src/router/agents/supervisor/README.md](src/router/agents/supervisor/README.md) |
| 性能层 | [src/router/agents/performance_layer/README.md](src/router/agents/performance_layer/README.md) |
| 工具注册 | [src/common/function_calls/README.md](src/common/function_calls/README.md) |
| 授权服务 | [src/router/services/authorization/README.md](src/router/services/authorization/README.md) |

---

## License

MIT License
