## src/core 目录说明

## 概述
该目录承载项目的“核心基础设施层”，主要包括：依赖注入、统一配置、指标采集与通用异常。

## 关键模块
- `dependencies.py`：基于 FastAPI `Depends` 的依赖注入封装（配置、SupervisorService、WorkerRegistry、指标采集等）。
- `settings.py`：统一配置中心（dataclass 形式），从环境变量加载并提供校验与类型安全访问。
- `metrics.py`：性能/运行指标采集与暴露（供 `/metrics` 使用）。
- `exceptions.py`：核心异常类型定义。

## 使用建议
- 路由层优先通过 `Depends` 注入服务与配置，减少全局状态与耦合。
