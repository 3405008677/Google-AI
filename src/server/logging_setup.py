"""集中管理服务器层的日志配置，避免重复配置处理器。"""

import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any

# 计算项目根目录及默认日志路径
BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_LOG_DIR = BASE_DIR / "log"
DEFAULT_LOG_FILE = DEFAULT_LOG_DIR / "server.log"


def _configure_logging(
    log_file: str = str(DEFAULT_LOG_FILE),
    log_level: int = logging.INFO,
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    log_encoding: str = "utf-8",
    file_mode: str = "a",
) -> None:
    """
    配置全局日志系统，确保只初始化一次

    Args:
        log_file: 日志文件路径
        log_level: 日志级别
        log_format: 日志格式字符串
        log_encoding: 日志文件编码
        file_mode: 日志文件打开模式 ('a' 追加, 'w' 覆盖)
    """
    # 防止重复添加处理器
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    # 确保日志目录存在
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # 创建格式化器
    formatter = logging.Formatter(log_format)

    # 文件处理器
    file_handler = logging.FileHandler(log_file, encoding=log_encoding, mode=file_mode)
    file_handler.setFormatter(formatter)

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # 配置根日志器
    root_logger.setLevel(log_level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def get_logger(name: Optional[str] = None, **kwargs: Dict[str, Any]) -> logging.Logger:
    """
    获取配置好的日志实例

    Args:
        name: 日志器名称，默认使用调用模块名
        **kwargs: 传递给 _configure_logging 的配置参数

    Returns:
        配置好的 Logger 实例
    """
    # 确保日志系统已初始化
    _configure_logging(**kwargs)

    # 如果未指定名称，使用调用模块名
    if name is None:
        import inspect

        frame = inspect.currentframe().f_back
        name = frame.f_globals.get('__name__', 'unknown')

    return logging.getLogger(name)


# 初始化默认日志配置
_configure_logging(log_file=str(DEFAULT_LOG_FILE))

# 创建默认日志实例
logger = get_logger(__name__)
