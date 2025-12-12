"""
Google AI 服务主模块

提供：
1. 配置管理
2. 核心异常
3. 服务器初始化
"""

from src.config import (
    AppConfig,
    get_config,
    get_local_ip,
    CustomizeModelConfig,
    get_customize_model_config,
    GeminiModelConfig,
    get_gemini_model_config,
    QwenModelConfig,
    get_qwen_model_config,
)

__version__ = "1.0.0"
__author__ = "PQJ"

__all__ = [
    # 版本信息
    "__version__",
    "__author__",
    
    # 配置
    "AppConfig",
    "get_config",
    "get_local_ip",
    "CustomizeModelConfig",
    "get_customize_model_config",
    "GeminiModelConfig",
    "get_gemini_model_config",
    "QwenModelConfig",
    "get_qwen_model_config",
]

