# src/core 目录

> 项目核心基础设施层：依赖注入、统一配置、指标采集。

---

## 设计理念

- **配置中心化**：所有配置通过 `settings` 单例访问，类型安全。
- **依赖注入**：利用 FastAPI 的 `Depends` 机制，解耦服务与路由。
- **可观测性**：内置指标采集，支持 Prometheus 格式输出。

---

## 文件结构

```
core/
├── __init__.py        # 统一导出
├── settings.py        # 配置中心（dataclass）
├── dependencies.py    # FastAPI 依赖注入
└── metrics.py         # 指标采集与暴露
```

---

## 配置中心 (settings.py)

### 特点

- **dataclass 定义**：强类型、IDE 友好、易于扩展。
- **环境变量加载**：自动从 `.env` 和系统环境变量读取。
- **启动校验**：缺少必要配置时输出友好警告。

### 使用示例

```python
from src.core import settings

# 访问配置
print(settings.HOST)           # 0.0.0.0
print(settings.PORT)           # 8080
print(settings.GEMINI_API_KEY) # xxx

# 检查模型是否可用
if settings.GEMINI_API_KEY:
    print("Gemini 已配置")
```

### 常用配置项

| 分类 | 配置项 | 说明 |
|:---|:---|:---|
| **服务器** | `HOST`, `PORT`, `WORKERS`, `DEBUG` | 服务监听参数 |
| **模型** | `GEMINI_API_KEY`, `QWEN_API_KEY` | 模型密钥 |
| **安全** | `JWT_SECRET_KEY`, `JWT_ALGORITHM` | JWT 签名 |
| **性能** | `REDIS_HOST`, `ENABLE_SEMANTIC_CACHE` | 缓存配置 |

---

## 依赖注入 (dependencies.py)

### 提供的依赖

```python
from src.core.dependencies import (
    get_settings,          # 获取配置
    get_supervisor_service,# 获取 Supervisor 服务
    get_worker_registry,   # 获取 Worker 注册表
    get_metrics_collector, # 获取指标采集器
)

# 在路由中使用
@router.post("/chat")
async def chat(
    service: SupervisorService = Depends(get_supervisor_service),
    settings: Settings = Depends(get_settings),
):
    ...
```

### 设计优势

- **可测试**：依赖可轻松 Mock。
- **懒加载**：服务按需创建，节省启动时间。
- **生命周期管理**：配合 FastAPI lifespan 自动清理。

---

## 指标采集 (metrics.py)

### 采集的指标

| 指标 | 类型 | 说明 |
|:---|:---|:---|
| `requests_total` | Counter | 请求总数 |
| `request_duration_seconds` | Histogram | 请求耗时分布 |
| `active_connections` | Gauge | 当前活跃连接数 |
| `llm_calls_total` | Counter | LLM 调用次数 |
| `cache_hits_total` | Counter | 缓存命中次数 |

### 暴露端点

指标通过 `/metrics` 端点暴露，支持 Prometheus 抓取：

```bash
curl http://localhost:8080/metrics
```
