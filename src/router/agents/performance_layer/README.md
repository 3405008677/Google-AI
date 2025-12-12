## src/router/agents/performance_layer 目录说明

## 概述
速通优化层（Performance Layer）：在进入昂贵的 LLM 调用前，先做“低成本决策”。

## 核心能力
- 规则引擎（Rule Engine）：匹配简单指令（问候/帮助/清除历史等）直接返回预设回答。
- 语义缓存（Semantic Cache）：将 Query 向量化并与历史查询比对，相似度超过阈值直接返回缓存答案。

## 关键文件
- `index.py`：`PerformanceLayer`、`SemanticCache`、`RuleEngine` 及中间件注册函数。

## 运行依赖
- 语义缓存依赖 Redis 与向量化模型（`sentence_transformers`）。未安装或连接失败会自动降级为禁用。
