"""
集中管理服务器层的日志配置

提供：
1. 统一的日志格式
2. 结构化日志支持
3. 日志轮转配置
4. 按模块分离日志文件
"""

import json
import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from typing import Optional, Dict, Any, Union


# === 常量定义 ===
BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_LOG_DIR = BASE_DIR / "log"
DEFAULT_LOG_FILE = DEFAULT_LOG_DIR / "server.log"

# 默认日志格式
DEFAULT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 日志级别映射
LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class StructuredFormatter(logging.Formatter):
    """
    结构化日志格式器
    
    输出 JSON 格式的日志，便于日志聚合和分析工具（如 ELK、Loki）处理。
    """
    
    def __init__(
        self,
        include_timestamp: bool = True,
        include_level: bool = True,
        include_name: bool = True,
        include_extra: bool = True,
    ):
        super().__init__()
        self.include_timestamp = include_timestamp
        self.include_level = include_level
        self.include_name = include_name
        self.include_extra = include_extra
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录为 JSON"""
        log_data: Dict[str, Any] = {}
        
        if self.include_timestamp:
            log_data["timestamp"] = datetime.utcnow().isoformat() + "Z"
        
        if self.include_level:
            log_data["level"] = record.levelname
        
        if self.include_name:
            log_data["logger"] = record.name
        
        log_data["message"] = record.getMessage()
        
        # 添加位置信息（仅在 DEBUG 级别）
        if record.levelno <= logging.DEBUG:
            log_data["location"] = {
                "file": record.filename,
                "line": record.lineno,
                "function": record.funcName,
            }
        
        # 添加异常信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # 添加额外字段
        if self.include_extra:
            extra_fields = {
                key: value
                for key, value in record.__dict__.items()
                if key not in {
                    "name", "msg", "args", "created", "filename", "funcName",
                    "levelname", "levelno", "lineno", "module", "msecs",
                    "pathname", "process", "processName", "relativeCreated",
                    "stack_info", "exc_info", "exc_text", "thread", "threadName",
                    "message", "asctime",
                }
            }
            if extra_fields:
                log_data["extra"] = extra_fields
        
        return json.dumps(log_data, ensure_ascii=False, default=str)


class ColoredFormatter(logging.Formatter):
    """
    带颜色的控制台日志格式器
    
    为不同日志级别添加 ANSI 颜色代码，提升可读性。
    """
    
    # ANSI 颜色代码
    COLORS = {
        "DEBUG": "\033[36m",     # 青色
        "INFO": "\033[32m",      # 绿色
        "WARNING": "\033[33m",   # 黄色
        "ERROR": "\033[31m",     # 红色
        "CRITICAL": "\033[41m",  # 红色背景
    }
    RESET = "\033[0m"
    
    def __init__(self, fmt: str = DEFAULT_FORMAT, datefmt: str = DEFAULT_DATE_FORMAT):
        super().__init__(fmt, datefmt)
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录，添加颜色"""
        # 保存原始 levelname
        original_levelname = record.levelname
        
        # 添加颜色
        color = self.COLORS.get(record.levelname, "")
        if color:
            record.levelname = f"{color}{record.levelname}{self.RESET}"
        
        # 格式化
        result = super().format(record)
        
        # 恢复原始 levelname
        record.levelname = original_levelname
        
        return result


def _configure_logging(
    log_file: Union[str, Path] = DEFAULT_LOG_FILE,
    log_level: Union[int, str] = logging.INFO,
    log_format: str = DEFAULT_FORMAT,
    log_encoding: str = "utf-8",
    enable_console: bool = True,
    enable_file: bool = True,
    enable_color: bool = True,
    enable_structured: bool = False,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
) -> None:
    """
    配置全局日志系统
    
    Args:
        log_file: 日志文件路径
        log_level: 日志级别（数字或字符串）
        log_format: 日志格式字符串
        log_encoding: 日志文件编码
        enable_console: 是否启用控制台输出
        enable_file: 是否启用文件输出
        enable_color: 是否启用控制台颜色
        enable_structured: 是否启用结构化日志（JSON 格式）
        max_bytes: 单个日志文件最大字节数（用于轮转）
        backup_count: 保留的日志文件数量
    """
    # 防止重复配置
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return
    
    # 解析日志级别
    if isinstance(log_level, str):
        log_level = LOG_LEVEL_MAP.get(log_level.upper(), logging.INFO)
    
    # 确保日志目录存在
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 配置根日志器
    root_logger.setLevel(log_level)
    
    # 创建格式化器
    if enable_structured:
        file_formatter = StructuredFormatter()
    else:
        file_formatter = logging.Formatter(log_format, DEFAULT_DATE_FORMAT)
    
    console_formatter = ColoredFormatter(log_format) if enable_color else logging.Formatter(log_format, DEFAULT_DATE_FORMAT)
    
    # 文件处理器（带轮转）
    if enable_file:
        file_handler = RotatingFileHandler(
            str(log_path),
            encoding=log_encoding,
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(log_level)
        root_logger.addHandler(file_handler)
    
    # 控制台处理器
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(log_level)
        root_logger.addHandler(console_handler)
    
    # 降低第三方库的日志级别
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(
    name: Optional[str] = None,
    log_file: Optional[Union[str, Path]] = None,
    **kwargs,
) -> logging.Logger:
    """
    获取配置好的日志实例
    
    Args:
        name: 日志器名称，默认使用调用模块名
        log_file: 可选的独立日志文件（用于按模块分离日志）
        **kwargs: 传递给 _configure_logging 的配置参数
    
    Returns:
        配置好的 Logger 实例
    """
    # 确保日志系统已初始化
    _configure_logging(**kwargs)
    
    # 获取日志器名称
    if name is None:
        import inspect
        frame = inspect.currentframe()
        if frame and frame.f_back:
            name = frame.f_back.f_globals.get("__name__", "unknown")
        else:
            name = "unknown"
    
    logger = logging.getLogger(name)
    
    # 如果指定了独立日志文件，添加额外的文件处理器
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 检查是否已经添加了该文件的处理器
        handler_exists = any(
            isinstance(h, logging.FileHandler) and h.baseFilename == str(log_path.resolve())
            for h in logger.handlers
        )
        
        if not handler_exists:
            file_handler = RotatingFileHandler(
                str(log_path),
                encoding="utf-8",
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
            )
            file_handler.setFormatter(logging.Formatter(DEFAULT_FORMAT, DEFAULT_DATE_FORMAT))
            logger.addHandler(file_handler)
    
    return logger


def log_with_context(
    logger: logging.Logger,
    level: int,
    message: str,
    **context,
) -> None:
    """
    带上下文信息的日志记录
    
    Args:
        logger: 日志器实例
        level: 日志级别
        message: 日志消息
        **context: 上下文信息（会添加到 extra 字段）
    """
    logger.log(level, message, extra=context)


# === 初始化 ===

# 初始化默认日志配置
_configure_logging(log_file=str(DEFAULT_LOG_FILE))

# 创建默认日志实例
logger = get_logger(__name__)


__all__ = [
    "logger",
    "get_logger",
    "log_with_context",
    "StructuredFormatter",
    "ColoredFormatter",
    "DEFAULT_LOG_DIR",
    "DEFAULT_LOG_FILE",
]
