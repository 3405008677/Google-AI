"""
日志工具函数

包含所有与日志记录相关的通用工具函数。
"""
import logging
from pathlib import Path
from typing import Optional

from fastapi import Request

from ..common.models.chat_models import ChatRequest
from .request_utils import extract_latest_question


def init_access_logger(service_name: str, log_filename: Optional[str] = None) -> logging.Logger:
    """
    为指定服务初始化专用日志文件
    
    Args:
        service_name: 服务名称（如 "Bailian", "SelfHosted"）
        log_filename: 日志文件名，如果不提供则使用 {service_name}.log
        
    Returns:
        logging.Logger: 配置好的日志器
    """
    log_dir = Path(__file__).resolve().parents[3] / "log"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / (log_filename or f"{service_name}.log")
    access_logger = logging.getLogger(f"{service_name}Access")

    if not any(
        isinstance(handler, logging.FileHandler) and Path(getattr(handler, "baseFilename", "")) == log_file
        for handler in access_logger.handlers
    ):
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(formatter)
        access_logger.addHandler(file_handler)
        access_logger.setLevel(logging.INFO)
        # 防止重复向根日志器传播，避免日志重复
        access_logger.propagate = False

    return access_logger


def log_request_metadata(
    endpoint: str,
    http_request: Request,
    chat_request: ChatRequest,
    service_name: str,
    access_logger: Optional[logging.Logger] = None
) -> None:
    """
    记录发起 AI 提问的基础信息
    
    Args:
        endpoint: 端点名称（如 "chat", "chat_stream"）
        http_request: FastAPI Request 对象
        chat_request: 聊天请求对象
        service_name: 服务名称
        access_logger: 可选的访问日志器，如果提供则同时写入访问日志
    """
    client_ip = http_request.client.host if http_request.client else "unknown"
    relative_path = str(http_request.url.path)
    question = extract_latest_question(chat_request).replace("\n", " ")
    log_message = f"endpoint={endpoint} ip={client_ip} path={relative_path} question={question}"
    
    logger = logging.getLogger(__name__)
    logger.info(log_message)
    
    if access_logger:
        access_logger.info(log_message)

