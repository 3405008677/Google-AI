"""
依赖注入模块

使用 FastAPI 的 Depends 模式提供服务依赖，优势：
1. 更好的可测试性（可以轻松注入 mock）
2. 延迟初始化（按需创建）
3. 请求级别的生命周期管理
4. 清晰的依赖关系

使用方式：
    from src.core.dependencies import get_supervisor_service, get_config_dep
    
    @router.post("/chat")
    async def chat(
        request: ChatRequest,
        service: SupervisorService = Depends(get_supervisor_service),
        config: AppConfig = Depends(get_config_dep),
    ):
        result = await service.run(request.message)
        return result
"""

from typing import Optional, Generator, AsyncGenerator
from functools import lru_cache

from fastapi import Depends, Request


# === 配置依赖 ===

def get_config_dep():
    """
    获取应用配置（依赖注入版本）
    
    Returns:
        AppConfig 实例
    """
    from src.config import get_config
    return get_config()


def get_customize_model_config_dep():
    """获取自定义模型配置"""
    from src.config import get_customize_model_config
    return get_customize_model_config()


def get_gemini_model_config_dep():
    """获取 Gemini 模型配置"""
    from src.config import get_gemini_model_config
    return get_gemini_model_config()


def get_qwen_model_config_dep():
    """获取 Qwen 模型配置"""
    from src.config import get_qwen_model_config
    return get_qwen_model_config()


# === Worker Registry 依赖 ===

def get_worker_registry_dep():
    """
    获取 Worker 注册表（依赖注入版本）
    
    Returns:
        WorkerRegistry 实例
    """
    from src.router.agents.supervisor.registry import get_registry
    return get_registry()


def ensure_workers_registered_dep(registry = Depends(get_worker_registry_dep)):
    """
    确保 Workers 已注册的依赖
    
    使用方式：
        @router.post("/chat")
        async def chat(
            _: None = Depends(ensure_workers_registered_dep),
        ):
            pass
    """
    if registry.is_empty():
        from src.router.agents.supervisor import register_all_workers
        register_all_workers()
    return None


# === Supervisor Service 依赖 ===

def get_supervisor_service_dep():
    """
    获取 Supervisor 服务（依赖注入版本）
    
    Returns:
        SupervisorService 实例
    """
    from src.router.agents.supervisor.service import get_service
    return get_service()


async def get_supervisor_service_with_init_dep(
    _: None = Depends(ensure_workers_registered_dep),
):
    """
    获取已初始化的 Supervisor 服务
    
    会自动确保 Workers 已注册。
    
    Returns:
        SupervisorService 实例
    """
    from src.router.agents.supervisor.service import get_service
    return get_service()


# === Performance Layer 依赖 ===

def get_performance_layer_dep():
    """
    获取 Performance Layer（依赖注入版本）
    
    Returns:
        PerformanceLayer 实例，如果未启用则返回 None
    """
    try:
        from src.router.agents.performance_layer import get_performance_layer
        return get_performance_layer()
    except Exception:
        return None


# === Metrics 依赖 ===

def get_metrics_collector_dep():
    """
    获取指标收集器（依赖注入版本）
    
    Returns:
        MetricsCollector 实例
    """
    from src.core.metrics import get_metrics_collector
    return get_metrics_collector()


# === 日志依赖 ===

def get_logger_dep(name: Optional[str] = None):
    """
    获取日志器工厂函数
    
    Args:
        name: 日志器名称
        
    Returns:
        Logger 实例
    """
    from src.server.logging_setup import get_logger
    return get_logger(name)


# === Request Context 依赖 ===

async def get_request_context_dep(request: Request):
    """
    从 HTTP 请求中提取上下文信息
    
    Returns:
        包含 trace_id、client_ip 等信息的字典
    """
    return {
        "trace_id": getattr(request.state, "trace_id", None),
        "client_ip": request.client.host if request.client else "unknown",
        "user_agent": request.headers.get("user-agent", "unknown"),
        "auth_token": getattr(request.state, "auth_token", None),
    }


def get_user_context_dep(request: Request):
    """
    构建用户上下文（依赖注入版本）
    
    从请求中提取用户相关信息。
    
    Returns:
        UserContext 字典
    """
    from src.router.agents.supervisor.state import UserContext, DEFAULT_USER_CONTEXT
    
    context: UserContext = {
        **DEFAULT_USER_CONTEXT,
        "session_id": getattr(request.state, "trace_id", None),
    }
    
    # 如果有认证信息
    if hasattr(request.state, "auth_token"):
        context["preferences"]["auth_token"] = request.state.auth_token
    
    return context


# === 服务容器类（可选的高级用法）===

class ServiceContainer:
    """
    服务容器
    
    集中管理所有服务的生命周期，支持：
    - 延迟初始化
    - 依赖替换（用于测试）
    - 生命周期管理
    """
    
    _instance: Optional['ServiceContainer'] = None
    
    def __init__(self):
        self._services: dict = {}
        self._overrides: dict = {}
    
    @classmethod
    def get_instance(cls) -> 'ServiceContainer':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def override(self, name: str, service):
        """
        覆盖服务（用于测试）
        
        Args:
            name: 服务名称
            service: 替代服务实例
        """
        self._overrides[name] = service
    
    def clear_overrides(self):
        """清除所有覆盖"""
        self._overrides.clear()
    
    def get_config(self):
        """获取配置"""
        if "config" in self._overrides:
            return self._overrides["config"]
        from src.config import get_config
        return get_config()
    
    def get_supervisor_service(self):
        """获取 Supervisor 服务"""
        if "supervisor_service" in self._overrides:
            return self._overrides["supervisor_service"]
        from src.router.agents.supervisor.service import get_service
        return get_service()
    
    def get_worker_registry(self):
        """获取 Worker 注册表"""
        if "worker_registry" in self._overrides:
            return self._overrides["worker_registry"]
        from src.router.agents.supervisor.registry import get_registry
        return get_registry()
    
    def get_performance_layer(self):
        """获取 Performance Layer"""
        if "performance_layer" in self._overrides:
            return self._overrides["performance_layer"]
        try:
            from src.router.agents.performance_layer import get_performance_layer
            return get_performance_layer()
        except Exception:
            return None
    
    def get_metrics_collector(self):
        """获取指标收集器"""
        if "metrics_collector" in self._overrides:
            return self._overrides["metrics_collector"]
        from src.core.metrics import get_metrics_collector
        return get_metrics_collector()


def get_service_container_dep() -> ServiceContainer:
    """获取服务容器依赖"""
    return ServiceContainer.get_instance()


# === 导出 ===

__all__ = [
    # 配置依赖
    "get_config_dep",
    "get_customize_model_config_dep",
    "get_gemini_model_config_dep",
    "get_qwen_model_config_dep",
    
    # Worker 依赖
    "get_worker_registry_dep",
    "ensure_workers_registered_dep",
    
    # 服务依赖
    "get_supervisor_service_dep",
    "get_supervisor_service_with_init_dep",
    "get_performance_layer_dep",
    "get_metrics_collector_dep",
    
    # 上下文依赖
    "get_request_context_dep",
    "get_user_context_dep",
    "get_logger_dep",
    
    # 服务容器
    "ServiceContainer",
    "get_service_container_dep",
]

