"""
核心模块

提供：
1. 统一配置中心
2. 统一异常处理
3. 错误码定义
4. 性能指标收集
5. 依赖注入
"""

from src.core.exceptions import (
    AppError,
    ErrorCode,
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    RateLimitError,
    ExternalServiceError,
    ConfigurationError,
    WorkerExecutionError,
    SupervisorError,
)

from src.core.metrics import (
    MetricsCollector,
    metrics,
    get_metrics_collector,
)

from src.core.settings import (
    Settings,
    settings,
    get_settings,
    reload_settings,
)

from src.core.dependencies import (
    get_config_dep,
    get_supervisor_service_dep,
    get_worker_registry_dep,
    get_performance_layer_dep,
    ServiceContainer,
)

__all__ = [
    # 配置
    "Settings",
    "settings",
    "get_settings",
    "reload_settings",
    
    # 异常
    "AppError",
    "ErrorCode",
    "ValidationError",
    "AuthenticationError",
    "AuthorizationError",
    "NotFoundError",
    "RateLimitError",
    "ExternalServiceError",
    "ConfigurationError",
    "WorkerExecutionError",
    "SupervisorError",
    
    # 指标
    "MetricsCollector",
    "metrics",
    "get_metrics_collector",
    
    # 依赖注入
    "get_config_dep",
    "get_supervisor_service_dep",
    "get_worker_registry_dep",
    "get_performance_layer_dep",
    "ServiceContainer",
]

