"""
Supervisor Architecture - LLM Factory

动态 LLM 创建工厂，根据用户上下文选择对应的模型。

支持的模型来源：
1. Customize (SELF_MODEL_*) - 自定义模型
2. Qwen (QWEN_*) - 通义千问
3. Gemini (GEMINI_*) - Google Gemini

使用方式：
    from src.router.agents.supervisor.llm_factory import create_llm_from_context
    
    # 在 Worker 中
    llm = create_llm_from_context(state.get("user_context"), temperature=0.5)
"""

import os
from typing import Optional, Dict, Any
import httpx
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel
from src.server.logging_setup import logger


# === 常量定义 ===
_SAFE_USER_AGENT = "python-httpx/0.28.0"
_HTTP_TIMEOUT = 60.0

# 复用 AsyncClient，避免每次建连带来的额外延迟
_shared_async_client: Optional[httpx.AsyncClient] = None

# 默认 API 端点
_DEFAULT_QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
_DEFAULT_QWEN_MODEL = "qwen-plus"


def _create_no_proxy_client() -> httpx.AsyncClient:
    """
    创建不使用系统代理的 HTTP 客户端
    
    用于绕过系统代理设置，直接连接到 API 服务器。
    """
    global _shared_async_client
    if _shared_async_client is None or _shared_async_client.is_closed:
        _shared_async_client = httpx.AsyncClient(proxy=None, timeout=_HTTP_TIMEOUT)
    return _shared_async_client


def _validate_ascii(value: Optional[str], name: str) -> Optional[str]:
    """
    验证字符串是否只包含 ASCII 字符
    
    HTTP headers 只能包含 ASCII 字符，非 ASCII 字符会导致 UnicodeEncodeError。
    """
    if value is None:
        return None
    
    try:
        value.encode('ascii')
    except UnicodeEncodeError:
        non_ascii = [(i, c, hex(ord(c))) for i, c in enumerate(value) if ord(c) > 127]
        details = ", ".join([f"位置{i}:'{c}'({h})" for i, c, h in non_ascii[:5]])
        raise ValueError(
            f"环境变量 {name} 包含非 ASCII 字符: {details}。"
            f"HTTP headers 只能使用 ASCII 字符。请检查 .env 文件。"
        )
    
    return value


def _get_env_validated(name: str, default: Optional[str] = None) -> Optional[str]:
    """获取环境变量并验证 ASCII"""
    value = os.getenv(name, default)
    return _validate_ascii(value, name)


class ModelConfig:
    """模型配置类"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: str = "default-model",
        source: str = "unknown",
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name
        self.source = source
    
    def is_valid(self) -> bool:
        """检查配置是否有效（至少需要 API key）"""
        return bool(self.api_key)
    
    def __repr__(self) -> str:
        return f"ModelConfig(source={self.source}, model={self.model_name}, base_url={self.base_url})"


def get_model_config_from_context(
    user_context: Optional[Dict[str, Any]] = None,
) -> ModelConfig:
    """
    从用户上下文中获取模型配置
    
    优先级：
    1. user_context["preferences"]["custom_model"] - 请求级别配置
    2. user_context["preferences"]["model_source"] - 指定模型来源
    3. 环境变量预设值
    
    Args:
        user_context: 用户上下文
        
    Returns:
        ModelConfig 实例
    """
    if user_context is None:
        user_context = {}
    
    preferences = user_context.get("preferences", {})
    
    # 1. 检查是否有 custom_model（来自 Customize 路由）
    custom_model = preferences.get("custom_model")
    if custom_model and custom_model.get("api_key"):
        logger.debug(f"[LLM Factory] 使用 Customize 模型: {custom_model.get('model_name')}")
        return ModelConfig(
            api_key=_validate_ascii(custom_model.get("api_key"), "custom_model.api_key"),
            base_url=_validate_ascii(custom_model.get("base_url"), "custom_model.base_url"),
            model_name=custom_model.get("model_name", "default-model"),
            source="customize",
        )
    
    # 2. 检查是否有 qwen_model（来自 Qwen 路由）
    qwen_model = preferences.get("qwen_model")
    if qwen_model and qwen_model.get("api_key"):
        logger.debug(f"[LLM Factory] 使用 Qwen 模型: {qwen_model.get('model_name')}")
        return ModelConfig(
            api_key=_validate_ascii(qwen_model.get("api_key"), "qwen_model.api_key"),
            base_url=_validate_ascii(
                qwen_model.get("base_url", _DEFAULT_QWEN_BASE_URL),
                "qwen_model.base_url"
            ),
            model_name=qwen_model.get("model_name", _DEFAULT_QWEN_MODEL),
            source="qwen",
        )
    
    # 3. 检查是否指定了模型来源
    model_source = preferences.get("model_source", "").lower()
    
    if model_source == "customize" or model_source == "self":
        # 使用自定义模型环境变量
        api_key = _get_env_validated("SELF_MODEL_API_KEY")
        if api_key:
            return ModelConfig(
                api_key=api_key,
                base_url=_get_env_validated("SELF_MODEL_BASE_URL"),
                model_name=os.getenv("SELF_MODEL_NAME", "default-model"),
                source="customize",
            )
    
    elif model_source == "qwen":
        # 使用 Qwen 环境变量
        api_key = _get_env_validated("QWEN_API_KEY")
        if api_key:
            return ModelConfig(
                api_key=api_key,
                base_url=_get_env_validated("QWEN_BASE_URL", _DEFAULT_QWEN_BASE_URL),
                model_name=os.getenv("QWEN_MODEL", _DEFAULT_QWEN_MODEL),
                source="qwen",
            )
    
    # 4. 预设：按顺序尝试各个模型
    # 顺序：Customize > Qwen
    
    # 尝试 Customize
    self_api_key = _get_env_validated("SELF_MODEL_API_KEY")
    self_base_url = _get_env_validated("SELF_MODEL_BASE_URL")
    if self_api_key and self_base_url:
        logger.debug("[LLM Factory] 使用预设 Customize 模型")
        return ModelConfig(
            api_key=self_api_key,
            base_url=self_base_url,
            model_name=os.getenv("SELF_MODEL_NAME", "default-model"),
            source="customize",
        )
    
    # 尝试 Qwen
    qwen_api_key = _get_env_validated("QWEN_API_KEY")
    if qwen_api_key:
        logger.debug("[LLM Factory] 使用预设 Qwen 模型")
        return ModelConfig(
            api_key=qwen_api_key,
            base_url=_get_env_validated("QWEN_BASE_URL", _DEFAULT_QWEN_BASE_URL),
            model_name=os.getenv("QWEN_MODEL", _DEFAULT_QWEN_MODEL),
            source="qwen",
        )
    
    # 没有配置任何模型，返回无效配置
    logger.warning("[LLM Factory] 没有配置任何有效的模型")
    return ModelConfig(
        api_key=None,
        base_url=None,
        model_name="",
        source="none",
    )


def create_llm_from_context(
    user_context: Optional[Dict[str, Any]] = None,
    temperature: float = 0.5,
    **kwargs,
) -> BaseChatModel:
    """
    根据用户上下文创建 LLM 实例
    
    这是 Workers 应该使用的主要函数。根据路由和配置自动选择正确的模型。
    
    Args:
        user_context: 用户上下文（来自 state["user_context"]）
        temperature: 温度参数
        **kwargs: 传递给 ChatOpenAI 的其他参数
        
    Returns:
        BaseChatModel 实例（ChatOpenAI）
        
    Raises:
        ValueError: 当没有配置任何有效的 API key 时
        
    Usage:
        # 在 Worker 中
        async def execute(self, state: SupervisorState) -> Dict[str, Any]:
            user_context = state.get("user_context", {})
            llm = create_llm_from_context(user_context, temperature=0.5)
            ...
    """
    config = get_model_config_from_context(user_context)
    
    if not config.is_valid():
        raise ValueError(
            "没有配置有效的 AI 模型。请设置以下环境变量之一：\n"
            "- SELF_MODEL_API_KEY + SELF_MODEL_BASE_URL（自定义模型）\n"
            "- QWEN_API_KEY（通义千问）"
        )
    
    logger.info(f"[LLM Factory] 创建 LLM: {config}")
    
    llm_kwargs = {
        "model": config.model_name,
        "api_key": config.api_key,
        "temperature": temperature,
        "http_async_client": _create_no_proxy_client(),  # 禁用系统代理
        "default_headers": {"User-Agent": _SAFE_USER_AGENT},  # 避免被 WAF 阻止
        **kwargs,
    }
    
    if config.base_url:
        llm_kwargs["base_url"] = config.base_url
    
    return ChatOpenAI(**llm_kwargs)


def create_llm_from_state(
    state: Dict[str, Any],
    temperature: float = 0.5,
    **kwargs,
) -> BaseChatModel:
    """
    从 SupervisorState 创建 LLM 实例
    
    这是一个便捷函数，直接从 state 提取 user_context。
    
    Args:
        state: SupervisorState 或包含 user_context 的字典
        temperature: 温度参数
        **kwargs: 传递给 ChatOpenAI 的其他参数
        
    Returns:
        BaseChatModel 实例
    """
    user_context = state.get("user_context", {})
    return create_llm_from_context(user_context, temperature, **kwargs)


# 导出公共接口
__all__ = [
    "create_llm_from_context",
    "create_llm_from_state",
    "get_model_config_from_context",
    "ModelConfig",
]

