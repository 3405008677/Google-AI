"""
Supervisor Architecture - LLM Factory

動態 LLM 創建工廠，根據用戶上下文選擇對應的模型。

支持的模型來源：
1. Customize (SELF_MODEL_*) - 自定義模型
2. Qwen (QWEN_*) - 通義千問
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


# === 常量定義 ===
_SAFE_USER_AGENT = "python-httpx/0.28.0"
_HTTP_TIMEOUT = 60.0

# 默認 API 端點
_DEFAULT_QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
_DEFAULT_QWEN_MODEL = "qwen-plus"


def _create_no_proxy_client() -> httpx.AsyncClient:
    """
    創建不使用系統代理的 HTTP 客戶端
    
    用於繞過系統代理設置，直接連接到 API 服務器。
    """
    return httpx.AsyncClient(proxy=None, timeout=_HTTP_TIMEOUT)


def _validate_ascii(value: Optional[str], name: str) -> Optional[str]:
    """
    驗證字符串是否只包含 ASCII 字符
    
    HTTP headers 只能包含 ASCII 字符，非 ASCII 字符會導致 UnicodeEncodeError。
    """
    if value is None:
        return None
    
    try:
        value.encode('ascii')
    except UnicodeEncodeError:
        non_ascii = [(i, c, hex(ord(c))) for i, c in enumerate(value) if ord(c) > 127]
        details = ", ".join([f"位置{i}:'{c}'({h})" for i, c, h in non_ascii[:5]])
        raise ValueError(
            f"環境變量 {name} 包含非 ASCII 字符: {details}。"
            f"HTTP headers 只能使用 ASCII 字符。請檢查 .env 文件。"
        )
    
    return value


def _get_env_validated(name: str, default: Optional[str] = None) -> Optional[str]:
    """獲取環境變量並驗證 ASCII"""
    value = os.getenv(name, default)
    return _validate_ascii(value, name)


class ModelConfig:
    """模型配置類"""
    
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
        """檢查配置是否有效（至少需要 API key）"""
        return bool(self.api_key)
    
    def __repr__(self) -> str:
        return f"ModelConfig(source={self.source}, model={self.model_name}, base_url={self.base_url})"


def get_model_config_from_context(
    user_context: Optional[Dict[str, Any]] = None,
) -> ModelConfig:
    """
    從用戶上下文中獲取模型配置
    
    優先級：
    1. user_context["preferences"]["custom_model"] - 請求級別配置
    2. user_context["preferences"]["model_source"] - 指定模型來源
    3. 環境變量預設值
    
    Args:
        user_context: 用戶上下文
        
    Returns:
        ModelConfig 實例
    """
    if user_context is None:
        user_context = {}
    
    preferences = user_context.get("preferences", {})
    
    # 1. 檢查是否有 custom_model（來自 Customize 路由）
    custom_model = preferences.get("custom_model")
    if custom_model and custom_model.get("api_key"):
        logger.debug(f"[LLM Factory] 使用 Customize 模型: {custom_model.get('model_name')}")
        return ModelConfig(
            api_key=_validate_ascii(custom_model.get("api_key"), "custom_model.api_key"),
            base_url=_validate_ascii(custom_model.get("base_url"), "custom_model.base_url"),
            model_name=custom_model.get("model_name", "default-model"),
            source="customize",
        )
    
    # 2. 檢查是否有 qwen_model（來自 Qwen 路由）
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
    
    # 3. 檢查是否指定了模型來源
    model_source = preferences.get("model_source", "").lower()
    
    if model_source == "customize" or model_source == "self":
        # 使用自定義模型環境變量
        api_key = _get_env_validated("SELF_MODEL_API_KEY")
        if api_key:
            return ModelConfig(
                api_key=api_key,
                base_url=_get_env_validated("SELF_MODEL_BASE_URL"),
                model_name=os.getenv("SELF_MODEL_NAME", "default-model"),
                source="customize",
            )
    
    elif model_source == "qwen":
        # 使用 Qwen 環境變量
        api_key = _get_env_validated("QWEN_API_KEY")
        if api_key:
            return ModelConfig(
                api_key=api_key,
                base_url=_get_env_validated("QWEN_BASE_URL", _DEFAULT_QWEN_BASE_URL),
                model_name=os.getenv("QWEN_MODEL", _DEFAULT_QWEN_MODEL),
                source="qwen",
            )
    
    # 4. 預設：按順序嘗試各個模型
    # 順序：Customize > Qwen
    
    # 嘗試 Customize
    self_api_key = _get_env_validated("SELF_MODEL_API_KEY")
    self_base_url = _get_env_validated("SELF_MODEL_BASE_URL")
    if self_api_key and self_base_url:
        logger.debug("[LLM Factory] 使用預設 Customize 模型")
        return ModelConfig(
            api_key=self_api_key,
            base_url=self_base_url,
            model_name=os.getenv("SELF_MODEL_NAME", "default-model"),
            source="customize",
        )
    
    # 嘗試 Qwen
    qwen_api_key = _get_env_validated("QWEN_API_KEY")
    if qwen_api_key:
        logger.debug("[LLM Factory] 使用預設 Qwen 模型")
        return ModelConfig(
            api_key=qwen_api_key,
            base_url=_get_env_validated("QWEN_BASE_URL", _DEFAULT_QWEN_BASE_URL),
            model_name=os.getenv("QWEN_MODEL", _DEFAULT_QWEN_MODEL),
            source="qwen",
        )
    
    # 沒有配置任何模型，返回無效配置
    logger.warning("[LLM Factory] 沒有配置任何有效的模型")
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
    根據用戶上下文創建 LLM 實例
    
    這是 Workers 應該使用的主要函數。根據路由和配置自動選擇正確的模型。
    
    Args:
        user_context: 用戶上下文（來自 state["user_context"]）
        temperature: 溫度參數
        **kwargs: 傳遞給 ChatOpenAI 的其他參數
        
    Returns:
        BaseChatModel 實例（ChatOpenAI）
        
    Raises:
        ValueError: 當沒有配置任何有效的 API key 時
        
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
            "沒有配置有效的 AI 模型。請設置以下環境變量之一：\n"
            "- SELF_MODEL_API_KEY + SELF_MODEL_BASE_URL（自定義模型）\n"
            "- QWEN_API_KEY（通義千問）"
        )
    
    logger.info(f"[LLM Factory] 創建 LLM: {config}")
    
    llm_kwargs = {
        "model": config.model_name,
        "api_key": config.api_key,
        "temperature": temperature,
        "http_async_client": _create_no_proxy_client(),  # 禁用系統代理
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
    從 SupervisorState 創建 LLM 實例
    
    這是一個便捷函數，直接從 state 提取 user_context。
    
    Args:
        state: SupervisorState 或包含 user_context 的字典
        temperature: 溫度參數
        **kwargs: 傳遞給 ChatOpenAI 的其他參數
        
    Returns:
        BaseChatModel 實例
    """
    user_context = state.get("user_context", {})
    return create_llm_from_context(user_context, temperature, **kwargs)


# 導出公共接口
__all__ = [
    "create_llm_from_context",
    "create_llm_from_state",
    "get_model_config_from_context",
    "ModelConfig",
]

