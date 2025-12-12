"""
应用配置管理模块

此模块负责：
1. 集中管理所有配置项（AppConfig、模型配置等）
2. 提供类型安全的配置访问
3. 支持环境变量和默认值
4. 配置验证和错误提示
"""

import os
import sys
import socket
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional, List

# 确保 Python 使用 UTF-8 编码（解决 Windows 上的中文编码问题）
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# Windows 控制台 UTF-8 支持
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from dotenv import load_dotenv

# 预先载入 .env，确保后续读取环境变量时皆已就绪
load_dotenv()

# 清理与系统 SSL 库冲突的环境变量
# SSL_CERT_FILE 和 SSL_KEY_FILE 是 httpx/requests 等库使用的标准环境变量
# 如果 .env 中设置了这些变量（即使是空值），会导致 SSL 验证失败
# 项目已改用 SERVER_SSL_CERTFILE / SERVER_SSL_KEYFILE 来避免冲突
for _conflict_var in ("SSL_CERT_FILE", "SSL_KEY_FILE"):
    if _conflict_var in os.environ:
        del os.environ[_conflict_var]

# 配置相关常量
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off"})


def _as_bool(value: Optional[str], default: bool = False) -> bool:
    """
    将字符串值转换为布尔值
    
    Args:
        value: 待转换的字符串，支持 "1", "true", "yes", "on" 为真
        default: 默认值
        
    Returns:
        转换后的布尔值
    """
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    return default


def _as_int(value: Optional[str], default: int, min_val: Optional[int] = None, max_val: Optional[int] = None) -> int:
    """
    将字符串值转换为整数，支持范围校验
    
    Args:
        value: 待转换的字符串
        default: 默认值
        min_val: 最小值（可选）
        max_val: 最大值（可选）
        
    Returns:
        转换后的整数
    """
    if value is None:
        return default
    try:
        result = int(value.strip())
        if min_val is not None and result < min_val:
            return min_val
        if max_val is not None and result > max_val:
            return max_val
        return result
    except (ValueError, AttributeError):
        return default


@dataclass(frozen=True)
class CustomizeModelConfig:
    """
    自建模型（OpenAI 兼容接口）配置
    
    Attributes:
        base_url: 自建模型 API 地址
        model_name: 模型名称
        api_key: API 密钥（可选，部分模型不需要）
        timeout: 请求超时时间（秒）
        max_retries: 最大重试次数
    """
    
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    api_key: Optional[str] = None
    timeout: int = 60
    max_retries: int = 3
    
    def is_configured(self) -> bool:
        """检查是否已配置自建模型"""
        return bool(self.base_url and self.model_name)
    
    def validate(self) -> List[str]:
        """
        验证配置，返回错误列表
        
        Returns:
            错误消息列表，空列表表示配置有效
        """
        errors = []
        if self.base_url and not self.base_url.startswith(("http://", "https://")):
            errors.append("base_url 必须以 http:// 或 https:// 开头")
        if self.timeout < 1:
            errors.append("timeout 必须大于 0")
        if self.max_retries < 0:
            errors.append("max_retries 不能为负数")
        return errors


@lru_cache(maxsize=1)
def get_customize_model_config() -> CustomizeModelConfig:
    """
    获取自定义模型配置（单例模式）
    
    Returns:
        CustomizeModelConfig 实例
    """
    config = CustomizeModelConfig(
        base_url=os.getenv("SELF_MODEL_BASE_URL"),
        model_name=os.getenv("SELF_MODEL_NAME"),
        api_key=os.getenv("SELF_MODEL_API_KEY"),
        timeout=_as_int(os.getenv("SELF_MODEL_TIMEOUT"), default=60, min_val=1),
        max_retries=_as_int(os.getenv("SELF_MODEL_MAX_RETRIES"), default=3, min_val=0),
    )
    
    # 配置验证
    errors = config.validate()
    if errors:
        logger = logging.getLogger(__name__)
        for error in errors:
            logger.warning(f"CustomizeModelConfig 配置警告: {error}")
    
    return config


@dataclass(frozen=True)
class GeminiModelConfig:
    """
    Gemini 模型配置
    
    Attributes:
        api_key: Gemini API 密钥
        model_name: 模型名称
        timeout: 请求超时时间（秒）
        max_retries: 最大重试次数
    """
    
    api_key: Optional[str] = None
    model_name: str = "gemini-2.5-flash"
    timeout: int = 60
    max_retries: int = 3
    
    def is_configured(self) -> bool:
        """检查是否已配置 Gemini"""
        return bool(self.api_key)
    
    def validate(self) -> List[str]:
        """验证配置，返回错误列表"""
        errors = []
        if self.timeout < 1:
            errors.append("timeout 必须大于 0")
        if self.max_retries < 0:
            errors.append("max_retries 不能为负数")
        return errors


@lru_cache(maxsize=1)
def get_gemini_model_config() -> GeminiModelConfig:
    """
    获取 Gemini 模型配置（单例模式）
    
    Returns:
        GeminiModelConfig 实例
    """
    return GeminiModelConfig(
        api_key=os.getenv("GEMINI_API_KEY"),
        model_name=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        timeout=_as_int(os.getenv("GEMINI_TIMEOUT"), default=60, min_val=1),
        max_retries=_as_int(os.getenv("GEMINI_MAX_RETRIES"), default=3, min_val=0),
    )


@dataclass(frozen=True)
class QwenModelConfig:
    """
    Qwen（通义千问）模型配置
    
    Attributes:
        api_key: Qwen API 密钥
        model_name: 模型名称
        base_url: API 地址
        timeout: 请求超时时间（秒）
        max_retries: 最大重试次数
    """
    
    api_key: Optional[str] = None
    model_name: str = "qwen-plus"
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    timeout: int = 60
    max_retries: int = 3
    
    def is_configured(self) -> bool:
        """检查是否已配置 Qwen"""
        return bool(self.api_key)
    
    def validate(self) -> List[str]:
        """验证配置，返回错误列表"""
        errors = []
        if self.base_url and not self.base_url.startswith(("http://", "https://")):
            errors.append("base_url 必须以 http:// 或 https:// 开头")
        if self.timeout < 1:
            errors.append("timeout 必须大于 0")
        if self.max_retries < 0:
            errors.append("max_retries 不能为负数")
        return errors


@lru_cache(maxsize=1)
def get_qwen_model_config() -> QwenModelConfig:
    """
    获取 Qwen 模型配置（单例模式）
    
    Returns:
        QwenModelConfig 实例
    """
    return QwenModelConfig(
        api_key=os.getenv("QWEN_API_KEY"),
        model_name=os.getenv("QWEN_MODEL", "qwen-plus"),
        base_url=os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        timeout=_as_int(os.getenv("QWEN_TIMEOUT"), default=60, min_val=1),
        max_retries=_as_int(os.getenv("QWEN_MAX_RETRIES"), default=3, min_val=0),
    )


@dataclass(frozen=True)
class AppConfig:
    """
    应用主配置类，集中管理所有应用级配置项
    
    Attributes:
        host: 服务器监听的主机地址
        port: 服务器监听的端口号
        debug: 是否启用调试模式
        enable_router: 是否在启动时加载路由
        static_dir: 静态文件目录路径
        max_upload_size: 最大上传文件大小（字节）
        ssl_enabled: 是否启用 SSL/HTTPS
        ssl_certfile: SSL 证书文件路径
        ssl_keyfile: SSL 私钥文件路径
        workers: 工作进程数
        log_level: 日志级别
    """

    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False
    enable_router: bool = False
    static_dir: Path = field(default_factory=lambda: Path("static"))
    max_upload_size: int = 1024 * 1024  # 1MB
    ssl_enabled: bool = False
    ssl_certfile: Optional[Path] = None
    ssl_keyfile: Optional[Path] = None
    workers: int = 1
    log_level: str = "INFO"
    
    def validate(self) -> List[str]:
        """
        验证配置，返回错误列表
        
        Returns:
            错误消息列表，空列表表示配置有效
        """
        errors = []
        
        # 端口范围校验
        if not (1 <= self.port <= 65535):
            errors.append(f"port 必须在 1-65535 范围内，当前值: {self.port}")
        
        # 上传大小校验
        if self.max_upload_size < 1024:
            errors.append("max_upload_size 至少为 1024 字节 (1KB)")
        
        # SSL 配置校验
        if self.ssl_enabled:
            if not self.ssl_certfile:
                errors.append("启用 SSL 时必须提供 ssl_certfile")
            elif not self.ssl_certfile.exists():
                errors.append(f"SSL 证书文件不存在: {self.ssl_certfile}")
            
            if not self.ssl_keyfile:
                errors.append("启用 SSL 时必须提供 ssl_keyfile")
            elif not self.ssl_keyfile.exists():
                errors.append(f"SSL 私钥文件不存在: {self.ssl_keyfile}")
        
        # Workers 校验
        if self.workers < 1:
            errors.append("workers 必须至少为 1")
        
        # 日志级别校验
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.log_level.upper() not in valid_levels:
            errors.append(f"log_level 必须是以下之一: {valid_levels}")
        
        return errors


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """
    获取应用配置（单例模式）
    
    配置优先级：环境变量 > 默认值
    
    Returns:
        AppConfig 实例
    """
    base_dir = Path(__file__).resolve().parent

    # 处理静态目录路径
    static_dir = Path(os.getenv("STATIC_DIR", "static"))
    if not static_dir.is_absolute():
        static_dir = base_dir.parent / static_dir

    # 处理 SSL 证书路径（使用 SERVER_ 前缀避免与系统 SSL_CERT_FILE 冲突）
    cert_path = os.getenv("SERVER_SSL_CERTFILE")
    key_path = os.getenv("SERVER_SSL_KEYFILE")

    config = AppConfig(
        host=os.getenv("HOST", "0.0.0.0"),
        port=_as_int(os.getenv("PORT"), default=8080, min_val=1, max_val=65535),
        debug=_as_bool(os.getenv("DEBUG"), default=False),
        enable_router=_as_bool(os.getenv("ENABLE_ROUTER"), default=True),
        static_dir=static_dir,
        max_upload_size=_as_int(os.getenv("MAX_UPLOAD_SIZE"), default=1024 * 1024, min_val=1024),
        ssl_enabled=_as_bool(os.getenv("SSL_ENABLED"), default=False),
        ssl_certfile=Path(cert_path).resolve() if cert_path else None,
        ssl_keyfile=Path(key_path).resolve() if key_path else None,
        workers=_as_int(os.getenv("WORKERS"), default=1, min_val=1),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
    
    # 配置验证
    errors = config.validate()
    if errors:
        logger = logging.getLogger(__name__)
        for error in errors:
            logger.warning(f"AppConfig 配置警告: {error}")
    
    return config


def get_local_ip() -> str:  # 获取本机局域网 IP 地址的函数
    """获取本机局域网 IP 地址"""
    try:  # 尝试第一种方法
        # 方法1: 通过连接外部地址获取本机 IP（最可靠）
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:  # 创建 UDP 套接字（IPv4）
            # 连接到一个公网地址（无需可达）以获取本地出口 IP
            s.connect(("8.8.8.8", 80))  # 连接到 Google DNS（不会真正发送数据）
            local_ip = s.getsockname()[0]  # 获取本地套接字的 IP 地址
            if local_ip and local_ip != "0.0.0.0":  # 如果获取到有效 IP 且不是回环地址
                return local_ip  # 返回获取到的 IP
    except Exception:  # 如果方法1失败
        pass  # 忽略异常，继续尝试方法2

    try:  # 尝试第二种方法
        # 方法2: 通过主机名获取 IP
        hostname = socket.gethostname()  # 获取本机主机名
        local_ip = socket.gethostbyname(hostname)  # 通过主机名解析 IP 地址
        if local_ip and local_ip != "0.0.0.0":  # 如果获取到有效 IP 且不是回环地址
            return local_ip  # 返回获取到的 IP
    except Exception:  # 如果方法2也失败
        pass  # 忽略异常，使用默认值

    # 回退到 localhost
    return "0.0.0.0"  # 返回本地回环地址作为默认值


__all__ = [
    "AppConfig", 
    "get_config", 
    "get_local_ip",
    "CustomizeModelConfig",
    "get_customize_model_config",
    "GeminiModelConfig",
    "get_gemini_model_config",
    "QwenModelConfig",
    "get_qwen_model_config",
]  # 定义模块的公共接口，控制 from module import * 时导入的内容
