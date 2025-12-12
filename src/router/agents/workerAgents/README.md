## src/router/agents/workerAgents 目录说明

## 概述
该目录用于存放具体 Worker/子图（sub-graph）实现，供 Supervisor 工作流调用。

## 关键文件
- `subgraphs.py`：若干 Worker 子图/子流程的组合与复用。

## 约定
- 新增 Worker/子图时，建议在这里集中维护，并在 `supervisor/registry.py` 中完成注册。
