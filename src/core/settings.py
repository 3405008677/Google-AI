"""
统一配置中心

将所有配置集中管理，提供：
1. 单一配置入口点
2. 环境感知配置
3. 配置验证
4. 热重载支持（可选）

使用方式：
    from src.core.settings import settings
    
    # 访问应用配置
    print(settings.app.port)
    
    # 访问模型配置
    print(settings.models.gemini.model)
    
    # 检查配置是否有效
    errors = settings.validate()
"""

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional, List, Dict, Any


# === 辅助函数 ===

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


def _env(key: str, default: str = "") -> str:
    """获取环境变量"""
    return os.getenv(key, default)


def _env_bool(key: str, default: bool = False) -> bool:
    """获取布尔环境变量"""
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in _TRUE_VALUES


def _env_int(key: str, default: int, min_val: Optional[int] = None, max_val: Optional[int] = None) -> int:
    """获取整数环境变量"""
    value = os.getenv(key)
    if value is None:
        return default
    try:
        result = int(value.strip())
        if min_val is not None:
            result = max(result, min_val)
        if max_val is not None:
            result = min(result, max_val)
        return result
    except ValueError:
        return default


def _env_float(key: str, default: float) -> float:
    """获取浮点数环境变量"""
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return float(value.strip())
    except ValueError:
        return default


# === 配置数据类 ===

@dataclass(frozen=True)
class ServerConfig:
    """服务器配置"""
    host: str = "0.0.0.0"
    port: int = 8080
    workers: int = 1
    debug: bool = False
    log_level: str = "INFO"


@dataclass(frozen=True)
class SSLConfig:
    """SSL 配置"""
    enabled: bool = False
    certfile: Optional[Path] = None
    keyfile: Optional[Path] = None


@dataclass(frozen=True)
class StaticConfig:
    """静态文件配置"""
    directory: Path = field(default_factory=lambda: Path("static"))
    max_upload_size: int = 1024 * 1024  # 1MB


@dataclass(frozen=True)
class GeminiConfig:
    """Gemini 模型配置"""
    api_key: Optional[str] = None
    model: str = "gemini-2.5-flash"
    timeout: int = 60
    max_retries: int = 3
    
    def is_configured(self) -> bool:
        return bool(self.api_key)


@dataclass(frozen=True)
class QwenConfig:
    """Qwen 模型配置"""
    api_key: Optional[str] = None
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model: str = "qwen-plus"
    timeout: int = 60
    max_retries: int = 3
    
    def is_configured(self) -> bool:
        return bool(self.api_key)


@dataclass(frozen=True)
class CustomModelConfig:
    """自定义模型配置"""
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    timeout: int = 60
    max_retries: int = 3
    
    def is_configured(self) -> bool:
        return bool(self.base_url and self.model)


@dataclass(frozen=True)
class ModelsConfig:
    """所有模型配置"""
    gemini: GeminiConfig = field(default_factory=GeminiConfig)
    qwen: QwenConfig = field(default_factory=QwenConfig)
    custom: CustomModelConfig = field(default_factory=CustomModelConfig)
    
    def get_available_models(self) -> List[str]:
        """获取已配置的模型列表"""
        available = []
        if self.gemini.is_configured():
            available.append("gemini")
        if self.qwen.is_configured():
            available.append("qwen")
        if self.custom.is_configured():
            available.append("custom")
        return available


@dataclass(frozen=True)
class RedisConfig:
    """Redis 配置"""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None
    
    @property
    def url(self) -> str:
        """获取 Redis URL"""
        auth = f":{self.password}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"


@dataclass(frozen=True)
class CacheConfig:
    """缓存配置"""
    enabled: bool = True
    similarity_threshold: float = 0.95
    ttl_days: int = 7


@dataclass(frozen=True)
class RuleEngineConfig:
    """规则引擎配置"""
    enabled: bool = True


@dataclass(frozen=True)
class TavilyConfig:
    """Tavily 搜索 API 配置"""
    api_key: Optional[str] = None
    max_results: int = 5
    search_depth: str = "basic"  # "basic" 或 "advanced"
    include_answer: bool = True
    include_raw_content: bool = False
    include_images: bool = False
    
    def is_configured(self) -> bool:
        return bool(self.api_key)


@dataclass(frozen=True)
class ToolsConfig:
    """工具配置"""
    tavily: TavilyConfig = field(default_factory=TavilyConfig)
    
    def get_available_tools(self) -> List[str]:
        """获取已配置的工具列表"""
        available = []
        if self.tavily.is_configured():
            available.append("tavily")
        return available


@dataclass(frozen=True)
class PerformanceConfig:
    """性能层配置"""
    redis: RedisConfig = field(default_factory=RedisConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    rule_engine: RuleEngineConfig = field(default_factory=RuleEngineConfig)


@dataclass(frozen=True)
class SupervisorConfig:
    """Supervisor 配置"""
    max_iterations: int = 10
    max_task_steps: int = 8
    enable_planning: bool = True


@dataclass(frozen=True)
class AuthConfig:
    """认证配置"""
    enabled: bool = True
    token: Optional[str] = None


@dataclass(frozen=True)
class RateLimitConfig:
    """限流配置"""
    enabled: bool = True
    requests_per_minute: int = 60
    requests_per_second: int = 10


@dataclass(frozen=True)
class SecurityConfig:
    """安全配置"""
    auth: AuthConfig = field(default_factory=AuthConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)


# === 主配置类 ===

@dataclass
class Settings:
    """
    统一配置中心
    
    集中管理所有配置，提供：
    - 类型安全的配置访问
    - 配置验证
    - 环境变量映射
    """
    
    # 服务器配置
    server: ServerConfig = field(default_factory=ServerConfig)
    ssl: SSLConfig = field(default_factory=SSLConfig)
    static: StaticConfig = field(default_factory=StaticConfig)
    
    # 模型配置
    models: ModelsConfig = field(default_factory=ModelsConfig)
    
    # 工具配置
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    
    # 功能配置
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    supervisor: SupervisorConfig = field(default_factory=SupervisorConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    
    # 功能开关
    enable_router: bool = False
    
    def validate(self) -> List[str]:
        """
        验证配置
        
        Returns:
            错误消息列表，空列表表示配置有效
        """
        errors = []
        
        # 服务器配置验证
        if not (1 <= self.server.port <= 65535):
            errors.append(f"server.port 必须在 1-65535 范围内，当前值: {self.server.port}")
        
        if self.server.workers < 1:
            errors.append("server.workers 必须至少为 1")
        
        # SSL 配置验证
        if self.ssl.enabled:
            if not self.ssl.certfile:
                errors.append("启用 SSL 时必须提供 ssl.certfile")
            elif self.ssl.certfile and not self.ssl.certfile.exists():
                errors.append(f"SSL 证书文件不存在: {self.ssl.certfile}")
            
            if not self.ssl.keyfile:
                errors.append("启用 SSL 时必须提供 ssl.keyfile")
            elif self.ssl.keyfile and not self.ssl.keyfile.exists():
                errors.append(f"SSL 私钥文件不存在: {self.ssl.keyfile}")
        
        # 模型配置验证
        if not self.models.get_available_models():
            errors.append("至少需要配置一个 AI 模型（gemini/qwen/custom）")
        
        # URL 格式验证
        for name, url in [
            ("models.qwen.base_url", self.models.qwen.base_url),
            ("models.custom.base_url", self.models.custom.base_url),
        ]:
            if url and not url.startswith(("http://", "https://")):
                errors.append(f"{name} 必须以 http:// 或 https:// 开头")
        
        return errors
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典（隐藏敏感信息）"""
        return {
            "server": {
                "host": self.server.host,
                "port": self.server.port,
                "workers": self.server.workers,
                "debug": self.server.debug,
            },
            "ssl": {
                "enabled": self.ssl.enabled,
            },
            "models": {
                "gemini": {"configured": self.models.gemini.is_configured()},
                "qwen": {"configured": self.models.qwen.is_configured()},
                "custom": {"configured": self.models.custom.is_configured()},
                "available": self.models.get_available_models(),
            },
            "tools": {
                "tavily": {"configured": self.tools.tavily.is_configured()},
                "available": self.tools.get_available_tools(),
            },
            "performance": {
                "cache_enabled": self.performance.cache.enabled,
                "rule_engine_enabled": self.performance.rule_engine.enabled,
            },
            "security": {
                "auth_enabled": self.security.auth.enabled,
                "rate_limit_enabled": self.security.rate_limit.enabled,
            },
            "enable_router": self.enable_router,
        }


# === 配置加载 ===

def _load_settings() -> Settings:
    """从环境变量加载配置"""
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    # 清理与系统 SSL 库冲突的环境变量
    for _conflict_var in ("SSL_CERT_FILE", "SSL_KEY_FILE"):
        if _conflict_var in os.environ:
            del os.environ[_conflict_var]
    
    base_dir = Path(__file__).resolve().parents[2]
    
    # 处理静态目录路径
    static_dir = Path(_env("STATIC_DIR", "static"))
    if not static_dir.is_absolute():
        static_dir = base_dir / static_dir
    
    # 处理 SSL 证书路径（使用 SERVER_ 前缀避免与系统 SSL_CERT_FILE 冲突）
    cert_path = _env("SERVER_SSL_CERTFILE")
    key_path = _env("SERVER_SSL_KEYFILE")
    
    return Settings(
        server=ServerConfig(
            host=_env("HOST", "0.0.0.0"),
            port=_env_int("PORT", 8080, min_val=1, max_val=65535),
            workers=_env_int("WORKERS", 1, min_val=1),
            debug=_env_bool("DEBUG", False),
            log_level=_env("LOG_LEVEL", "INFO").upper(),
        ),
        ssl=SSLConfig(
            enabled=_env_bool("SSL_ENABLED", False),
            certfile=Path(cert_path).resolve() if cert_path else None,
            keyfile=Path(key_path).resolve() if key_path else None,
        ),
        static=StaticConfig(
            directory=static_dir,
            max_upload_size=_env_int("MAX_UPLOAD_SIZE", 1024 * 1024, min_val=1024),
        ),
        models=ModelsConfig(
            gemini=GeminiConfig(
                api_key=_env("GEMINI_API_KEY"),
                model=_env("GEMINI_MODEL", "gemini-2.5-flash"),
                timeout=_env_int("GEMINI_TIMEOUT", 60, min_val=1),
                max_retries=_env_int("GEMINI_MAX_RETRIES", 3, min_val=0),
            ),
            qwen=QwenConfig(
                api_key=_env("QWEN_API_KEY"),
                base_url=_env("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
                model=_env("QWEN_MODEL", "qwen-plus"),
                timeout=_env_int("QWEN_TIMEOUT", 60, min_val=1),
                max_retries=_env_int("QWEN_MAX_RETRIES", 3, min_val=0),
            ),
            custom=CustomModelConfig(
                api_key=_env("SELF_MODEL_API_KEY"),
                base_url=_env("SELF_MODEL_BASE_URL") or None,
                model=_env("SELF_MODEL_NAME") or None,
                timeout=_env_int("SELF_MODEL_TIMEOUT", 60, min_val=1),
                max_retries=_env_int("SELF_MODEL_MAX_RETRIES", 3, min_val=0),
            ),
        ),
        tools=ToolsConfig(
            tavily=TavilyConfig(
                api_key=_env("TAVILY_API_KEY") or None,
                max_results=_env_int("TAVILY_MAX_RESULTS", 5, min_val=1, max_val=20),
                search_depth=_env("TAVILY_SEARCH_DEPTH", "basic"),
                include_answer=_env_bool("TAVILY_INCLUDE_ANSWER", True),
                include_raw_content=_env_bool("TAVILY_INCLUDE_RAW_CONTENT", False),
                include_images=_env_bool("TAVILY_INCLUDE_IMAGES", False),
            ),
        ),
        performance=PerformanceConfig(
            redis=RedisConfig(
                host=_env("REDIS_HOST", "localhost"),
                port=_env_int("REDIS_PORT", 6379),
                db=_env_int("REDIS_DB", 0),
                password=_env("REDIS_PASSWORD") or None,
            ),
            cache=CacheConfig(
                enabled=_env_bool("ENABLE_SEMANTIC_CACHE", True),
                similarity_threshold=_env_float("SEMANTIC_CACHE_THRESHOLD", 0.95),
                ttl_days=_env_int("CACHE_TTL_DAYS", 7),
            ),
            rule_engine=RuleEngineConfig(
                enabled=_env_bool("ENABLE_RULE_ENGINE", True),
            ),
        ),
        supervisor=SupervisorConfig(
            max_iterations=_env_int("SUPERVISOR_MAX_ITERATIONS", 10, min_val=1),
            max_task_steps=_env_int("SUPERVISOR_MAX_TASK_STEPS", 8, min_val=1),
            enable_planning=_env_bool("SUPERVISOR_ENABLE_PLANNING", True),
        ),
        security=SecurityConfig(
            auth=AuthConfig(
                enabled=_env_bool("AUTH_ENABLED", True),
                token=_env("AUTH_TOKEN") or None,
            ),
            rate_limit=RateLimitConfig(
                enabled=_env_bool("RATE_LIMIT_ENABLED", True),
                requests_per_minute=_env_int("RATE_LIMIT_RPM", 60, min_val=1),
                requests_per_second=_env_int("RATE_LIMIT_RPS", 10, min_val=1),
            ),
        ),
        enable_router=_env_bool("ENABLE_ROUTER", False),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    获取全局配置（单例模式）
    
    Returns:
        Settings 实例
    """
    return _load_settings()


def reload_settings() -> Settings:
    """
    重新加载配置（清除缓存）
    
    Returns:
        新的 Settings 实例
    """
    get_settings.cache_clear()
    return get_settings()


# 全局配置实例
settings = get_settings()


__all__ = [
    # 配置类
    "Settings",
    "ServerConfig",
    "SSLConfig",
    "StaticConfig",
    "ModelsConfig",
    "GeminiConfig",
    "QwenConfig",
    "CustomModelConfig",
    "ToolsConfig",
    "TavilyConfig",
    "PerformanceConfig",
    "RedisConfig",
    "CacheConfig",
    "RuleEngineConfig",
    "SupervisorConfig",
    "SecurityConfig",
    "AuthConfig",
    "RateLimitConfig",
    
    # 函数
    "get_settings",
    "reload_settings",
    
    # 实例
    "settings",
]

