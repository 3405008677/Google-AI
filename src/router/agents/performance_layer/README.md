# src/router/agents/performance_layer 目录

> 性能优化层：规则引擎 + 语义缓存，实现"0 Token"速通。

---

## 设计目标

在调用昂贵的 LLM 之前，先进行低成本判断：
- **降低成本**：重复/相似问题不重复调用 LLM。
- **降低延迟**：规则命中 < 1ms，缓存命中 < 10ms。
- **提升体验**：常见问题即时响应。

---

## 架构

```
                    用户请求
                        │
                        ▼
            ┌───────────────────────┐
            │   Performance Layer   │
            └───────────┬───────────┘
                        │
            ┌───────────▼───────────┐
            │     Rule Engine       │ ◀── 正则/关键字匹配
            │   (规则引擎)           │
            └───────────┬───────────┘
                        │
                命中？ ──┼── 未命中
                  │      │
                  ▼      ▼
              直接返回   继续
                        │
            ┌───────────▼───────────┐
            │    Semantic Cache     │ ◀── 向量相似度比对
            │   (语义缓存)           │
            └───────────┬───────────┘
                        │
                命中？ ──┼── 未命中
                  │      │
                  ▼      ▼
              直接返回   调用 LLM
```

---

## 文件结构

```
performance_layer/
├── __init__.py      # 导出
└── index.py         # PerformanceLayer, RuleEngine, SemanticCache
```

---

## 规则引擎 (Rule Engine)

### 功能

匹配预定义的简单意图，直接返回固定回答。

### 内置规则

| 规则 | 匹配模式 | 响应 |
|:---|:---|:---|
| 问候 | `你好`, `hi`, `hello` | "你好！有什么可以帮助你的？" |
| 帮助 | `帮助`, `help`, `使用说明` | 使用指南 |
| 清除历史 | `清除`, `重置`, `新对话` | "已清除对话历史" |

### 配置

```ini
# .env
ENABLE_RULE_ENGINE=true
```

### 自定义规则

```python
# 在 index.py 中添加
RULES = [
    {
        "pattern": r"(你好|hi|hello)",
        "response": "你好！有什么可以帮助你的？",
        "priority": 100,
    },
    {
        "pattern": r"(天气|weather)",
        "response": "抱歉，我目前无法查询天气。",
        "priority": 50,
    },
]
```

---

## 语义缓存 (Semantic Cache)

### 功能

将用户 Query 向量化，与历史问答比对：
- 相似度 > 阈值 → 返回缓存答案。
- 相似度 < 阈值 → 调用 LLM，并缓存结果。

### 工作流程

```
1. Query → 向量化（sentence-transformers）
2. → 在 Redis 中搜索相似向量
3. → 相似度 > 0.95？
   ├─ 是 → 返回缓存答案
   └─ 否 → 调用 LLM → 缓存结果
```

### 配置

```ini
# .env
ENABLE_SEMANTIC_CACHE=true
SEMANTIC_CACHE_THRESHOLD=0.95    # 相似度阈值（0-1）

# Redis 连接
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
```

### 依赖

| 依赖 | 说明 |
|:---|:---|
| `redis` | 缓存存储 |
| `sentence-transformers` | 文本向量化 |

### 降级策略

当 Redis 或向量模型不可用时，自动降级为禁用：

```python
try:
    self._init_redis()
    self._init_embedder()
except Exception as e:
    logger.warning(f"语义缓存初始化失败，已禁用: {e}")
    self.enabled = False
```

---

## API 使用

### 在 SupervisorService 中集成

```python
class SupervisorService:
    def __init__(self):
        self.performance_layer = PerformanceLayer()
    
    async def process(self, message: str, ...) -> str:
        # 1. 检查性能层
        cached = await self.performance_layer.check(message)
        if cached:
            return cached
        
        # 2. 调用 LLM
        response = await self._call_llm(message)
        
        # 3. 缓存结果
        await self.performance_layer.cache(message, response)
        
        return response
```

---

## 性能指标

| 场景 | 延迟 | Token 消耗 |
|:---|:---|:---|
| 规则命中 | < 1ms | 0 |
| 缓存命中 | < 10ms | 0 |
| 缓存未命中 | 取决于 LLM | 正常消耗 |

---

## 最佳实践

1. **阈值调优**：0.95 是推荐值，过低会导致误命中，过高则命中率下降。
2. **缓存过期**：建议设置合理的 TTL（如 24 小时），避免过期数据。
3. **监控命中率**：通过 `/metrics` 观察 `cache_hits_total` 指标。
4. **冷启动**：首次部署时缓存为空，可预热常见问题。
