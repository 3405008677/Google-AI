"""
统一异常处理模块

提供：
1. 标准化的错误码枚举
2. 分层异常类（业务异常、系统异常）
3. 异常处理器注册函数
4. 统一的错误响应格式
"""

from enum import Enum
from typing import Any, Dict, Optional
from dataclasses import dataclass, field


class ErrorCode(str, Enum):
    """
    标准化错误码枚举
    
    命名规则：{类型}_{模块}_{具体错误}
    
    类型前缀：
    - VAL: 验证错误 (4xx)
    - AUTH: 认证/授权错误 (401/403)
    - NOT_FOUND: 资源不存在 (404)
    - RATE_LIMIT: 限流错误 (429)
    - SVC: 服务错误 (5xx)
    - CFG: 配置错误
    """
    
    # === 验证错误 (400) ===
    VAL_INVALID_INPUT = "VAL_INVALID_INPUT"
    VAL_MISSING_FIELD = "VAL_MISSING_FIELD"
    VAL_INVALID_FORMAT = "VAL_INVALID_FORMAT"
    VAL_OUT_OF_RANGE = "VAL_OUT_OF_RANGE"
    
    # === 认证错误 (401) ===
    AUTH_MISSING_TOKEN = "AUTH_MISSING_TOKEN"
    AUTH_INVALID_TOKEN = "AUTH_INVALID_TOKEN"
    AUTH_EXPIRED_TOKEN = "AUTH_EXPIRED_TOKEN"
    AUTH_INVALID_FORMAT = "AUTH_INVALID_FORMAT"
    
    # === 授权错误 (403) ===
    AUTHZ_PERMISSION_DENIED = "AUTHZ_PERMISSION_DENIED"
    AUTHZ_RESOURCE_FORBIDDEN = "AUTHZ_RESOURCE_FORBIDDEN"
    
    # === 资源不存在 (404) ===
    NOT_FOUND_RESOURCE = "NOT_FOUND_RESOURCE"
    NOT_FOUND_WORKER = "NOT_FOUND_WORKER"
    NOT_FOUND_SESSION = "NOT_FOUND_SESSION"
    
    # === 限流错误 (429) ===
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    RATE_LIMIT_PER_SECOND = "RATE_LIMIT_PER_SECOND"
    RATE_LIMIT_PER_MINUTE = "RATE_LIMIT_PER_MINUTE"
    
    # === 服务错误 (500) ===
    SVC_INTERNAL_ERROR = "SVC_INTERNAL_ERROR"
    SVC_WORKER_EXECUTION = "SVC_WORKER_EXECUTION"
    SVC_SUPERVISOR_DECISION = "SVC_SUPERVISOR_DECISION"
    SVC_SUBGRAPH_EXECUTION = "SVC_SUBGRAPH_EXECUTION"
    SVC_LLM_INVOCATION = "SVC_LLM_INVOCATION"
    
    # === 外部服务错误 (502/503) ===
    EXT_LLM_UNAVAILABLE = "EXT_LLM_UNAVAILABLE"
    EXT_REDIS_UNAVAILABLE = "EXT_REDIS_UNAVAILABLE"
    EXT_DATABASE_UNAVAILABLE = "EXT_DATABASE_UNAVAILABLE"
    EXT_SEARCH_UNAVAILABLE = "EXT_SEARCH_UNAVAILABLE"
    
    # === 配置错误 ===
    CFG_MISSING_KEY = "CFG_MISSING_KEY"
    CFG_INVALID_VALUE = "CFG_INVALID_VALUE"
    CFG_INITIALIZATION_FAILED = "CFG_INITIALIZATION_FAILED"


# 错误码与 HTTP 状态码映射
ERROR_CODE_TO_STATUS: Dict[ErrorCode, int] = {
    # 400
    ErrorCode.VAL_INVALID_INPUT: 400,
    ErrorCode.VAL_MISSING_FIELD: 400,
    ErrorCode.VAL_INVALID_FORMAT: 400,
    ErrorCode.VAL_OUT_OF_RANGE: 400,
    
    # 401
    ErrorCode.AUTH_MISSING_TOKEN: 401,
    ErrorCode.AUTH_INVALID_TOKEN: 401,
    ErrorCode.AUTH_EXPIRED_TOKEN: 401,
    ErrorCode.AUTH_INVALID_FORMAT: 401,
    
    # 403
    ErrorCode.AUTHZ_PERMISSION_DENIED: 403,
    ErrorCode.AUTHZ_RESOURCE_FORBIDDEN: 403,
    
    # 404
    ErrorCode.NOT_FOUND_RESOURCE: 404,
    ErrorCode.NOT_FOUND_WORKER: 404,
    ErrorCode.NOT_FOUND_SESSION: 404,
    
    # 429
    ErrorCode.RATE_LIMIT_EXCEEDED: 429,
    ErrorCode.RATE_LIMIT_PER_SECOND: 429,
    ErrorCode.RATE_LIMIT_PER_MINUTE: 429,
    
    # 500
    ErrorCode.SVC_INTERNAL_ERROR: 500,
    ErrorCode.SVC_WORKER_EXECUTION: 500,
    ErrorCode.SVC_SUPERVISOR_DECISION: 500,
    ErrorCode.SVC_SUBGRAPH_EXECUTION: 500,
    ErrorCode.SVC_LLM_INVOCATION: 500,
    
    # 502/503
    ErrorCode.EXT_LLM_UNAVAILABLE: 503,
    ErrorCode.EXT_REDIS_UNAVAILABLE: 503,
    ErrorCode.EXT_DATABASE_UNAVAILABLE: 503,
    ErrorCode.EXT_SEARCH_UNAVAILABLE: 503,
    
    # 配置错误也返回 500
    ErrorCode.CFG_MISSING_KEY: 500,
    ErrorCode.CFG_INVALID_VALUE: 500,
    ErrorCode.CFG_INITIALIZATION_FAILED: 500,
}


@dataclass
class AppError(Exception):
    """
    应用统一异常基类
    
    所有自定义异常都应继承此类，确保：
    1. 统一的错误码
    2. 统一的错误消息格式
    3. 支持额外的上下文信息
    
    Attributes:
        code: 错误码（ErrorCode 枚举）
        message: 错误消息
        detail: 详细信息（可选）
        extra: 额外的上下文数据
    """
    
    code: ErrorCode
    message: str
    detail: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        super().__init__(self.message)
    
    @property
    def status_code(self) -> int:
        """获取对应的 HTTP 状态码"""
        return ERROR_CODE_TO_STATUS.get(self.code, 500)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（用于 API 响应）"""
        result = {
            "code": self.code.value,
            "message": self.message,
        }
        if self.detail:
            result["detail"] = self.detail
        if self.extra:
            result["extra"] = self.extra
        return result
    
    def __str__(self) -> str:
        return f"[{self.code.value}] {self.message}"


# === 具体异常类 ===

@dataclass
class ValidationError(AppError):
    """验证错误异常"""
    
    code: ErrorCode = ErrorCode.VAL_INVALID_INPUT
    message: str = "输入数据验证失败"
    field: Optional[str] = None
    
    def __post_init__(self):
        super().__post_init__()
        if self.field:
            self.extra["field"] = self.field


@dataclass
class AuthenticationError(AppError):
    """认证错误异常"""
    
    code: ErrorCode = ErrorCode.AUTH_INVALID_TOKEN
    message: str = "认证失败"


@dataclass
class AuthorizationError(AppError):
    """授权错误异常"""
    
    code: ErrorCode = ErrorCode.AUTHZ_PERMISSION_DENIED
    message: str = "权限不足"


@dataclass
class NotFoundError(AppError):
    """资源不存在异常"""
    
    code: ErrorCode = ErrorCode.NOT_FOUND_RESOURCE
    message: str = "资源不存在"
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    
    def __post_init__(self):
        super().__post_init__()
        if self.resource_type:
            self.extra["resource_type"] = self.resource_type
        if self.resource_id:
            self.extra["resource_id"] = self.resource_id


@dataclass
class RateLimitError(AppError):
    """限流错误异常"""
    
    code: ErrorCode = ErrorCode.RATE_LIMIT_EXCEEDED
    message: str = "请求过于频繁，请稍后再试"
    retry_after: Optional[int] = None
    
    def __post_init__(self):
        super().__post_init__()
        if self.retry_after:
            self.extra["retry_after"] = self.retry_after


@dataclass
class ExternalServiceError(AppError):
    """外部服务错误异常"""
    
    code: ErrorCode = ErrorCode.EXT_LLM_UNAVAILABLE
    message: str = "外部服务暂时不可用"
    service_name: Optional[str] = None
    
    def __post_init__(self):
        super().__post_init__()
        if self.service_name:
            self.extra["service"] = self.service_name


@dataclass
class ConfigurationError(AppError):
    """配置错误异常"""
    
    code: ErrorCode = ErrorCode.CFG_INVALID_VALUE
    message: str = "配置错误"
    config_key: Optional[str] = None
    
    def __post_init__(self):
        super().__post_init__()
        if self.config_key:
            self.extra["config_key"] = self.config_key


@dataclass
class WorkerExecutionError(AppError):
    """Worker 执行错误异常"""
    
    code: ErrorCode = ErrorCode.SVC_WORKER_EXECUTION
    message: str = "Worker 执行失败"
    worker_name: Optional[str] = None
    
    def __post_init__(self):
        super().__post_init__()
        if self.worker_name:
            self.extra["worker"] = self.worker_name


@dataclass
class SupervisorError(AppError):
    """Supervisor 决策错误异常"""
    
    code: ErrorCode = ErrorCode.SVC_SUPERVISOR_DECISION
    message: str = "Supervisor 决策失败"
    iteration_count: Optional[int] = None
    
    def __post_init__(self):
        super().__post_init__()
        if self.iteration_count is not None:
            self.extra["iteration_count"] = self.iteration_count


__all__ = [
    "ErrorCode",
    "ERROR_CODE_TO_STATUS",
    "AppError",
    "ValidationError",
    "AuthenticationError",
    "AuthorizationError",
    "NotFoundError",
    "RateLimitError",
    "ExternalServiceError",
    "ConfigurationError",
    "WorkerExecutionError",
    "SupervisorError",
]

