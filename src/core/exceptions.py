"""
统一异常处理模块

提供：
1. 错误码枚举
2. 基础应用异常
3. 各类业务异常
"""

from enum import Enum
from typing import Optional, Any, Dict


class ErrorCode(Enum):
    """错误码枚举"""
    
    # 通用错误 (1000-1999)
    UNKNOWN = 1000
    VALIDATION_ERROR = 1001
    CONFIGURATION_ERROR = 1002
    
    # 认证授权错误 (2000-2999)
    AUTHENTICATION_ERROR = 2000
    AUTHORIZATION_ERROR = 2001
    TOKEN_EXPIRED = 2002
    INVALID_TOKEN = 2003
    
    # 资源错误 (3000-3999)
    NOT_FOUND = 3000
    RESOURCE_EXISTS = 3001
    
    # 限流错误 (4000-4999)
    RATE_LIMIT_EXCEEDED = 4000
    
    # 外部服务错误 (5000-5999)
    EXTERNAL_SERVICE_ERROR = 5000
    API_CALL_FAILED = 5001
    TIMEOUT_ERROR = 5002
    
    # Worker/Supervisor 错误 (6000-6999)
    WORKER_EXECUTION_ERROR = 6000
    SUPERVISOR_ERROR = 6001
    WORKER_NOT_FOUND = 6002
    WORKER_TIMEOUT = 6003


class AppError(Exception):
    """应用基础异常类"""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.UNKNOWN,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.cause = cause
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "error": self.error_code.name,
            "code": self.error_code.value,
            "message": self.message,
            "details": self.details
        }
    
    def __str__(self) -> str:
        return f"[{self.error_code.name}] {self.message}"


class ValidationError(AppError):
    """验证错误"""
    
    def __init__(
        self,
        message: str = "Validation failed",
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.VALIDATION_ERROR,
            details=details,
            cause=cause
        )


class AuthenticationError(AppError):
    """认证错误"""
    
    def __init__(
        self,
        message: str = "Authentication failed",
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.AUTHENTICATION_ERROR,
            details=details,
            cause=cause
        )


class AuthorizationError(AppError):
    """授权错误"""
    
    def __init__(
        self,
        message: str = "Authorization failed",
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.AUTHORIZATION_ERROR,
            details=details,
            cause=cause
        )


class NotFoundError(AppError):
    """资源不存在错误"""
    
    def __init__(
        self,
        message: str = "Resource not found",
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.NOT_FOUND,
            details=details,
            cause=cause
        )


class RateLimitError(AppError):
    """限流错误"""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
            details=details,
            cause=cause
        )


class ExternalServiceError(AppError):
    """外部服务错误"""
    
    def __init__(
        self,
        message: str = "External service error",
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.EXTERNAL_SERVICE_ERROR,
            details=details,
            cause=cause
        )


class ConfigurationError(AppError):
    """配置错误"""
    
    def __init__(
        self,
        message: str = "Configuration error",
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.CONFIGURATION_ERROR,
            details=details,
            cause=cause
        )


class WorkerExecutionError(AppError):
    """Worker 执行错误"""
    
    def __init__(
        self,
        message: str = "Worker execution failed",
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.WORKER_EXECUTION_ERROR,
            details=details,
            cause=cause
        )


class SupervisorError(AppError):
    """Supervisor 错误"""
    
    def __init__(
        self,
        message: str = "Supervisor error",
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_code=ErrorCode.SUPERVISOR_ERROR,
            details=details,
            cause=cause
        )


__all__ = [
    "ErrorCode",
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

