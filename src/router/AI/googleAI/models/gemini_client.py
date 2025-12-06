from __future__ import annotations

import logging
from functools import lru_cache
from typing import Iterable

from google import genai

from src.config import get_config

logger = logging.getLogger(__name__)


class GeminiClientError(RuntimeError):
    """Raised when Gemini API 操作失败"""


class GeminiClient:
    """封装 Gemini 文字生成功能"""

    def __init__(self, api_key: str, model: str):
        # 在初始化阶段立即验证 API Key，以便提早失败
        if not api_key:
            raise GeminiClientError("尚未提供 GEMINI_API_KEY，无法建立客户端。")

        self._model = model
        try:
            self._client = genai.Client(api_key=api_key)
        except Exception as exc:  # pragma: no cover - 第三方例外直接冒泡
            raise GeminiClientError(f"初始化 Gemini 客户端失败: {exc}") from exc

    def _new_session(self):
        """确保每次呼叫都产生新的聊天 session，避免状态污染。"""
        try:
            return self._client.chats.create(model=self._model)
        except Exception as exc:
            raise GeminiClientError(f"建立聊天会话失败: {exc}") from exc

    def generate_text(self, prompt: str) -> str:
        """同步生成整段回复，适合短内容。"""
        if not prompt.strip():
            raise ValueError("输入内容不可为空白。")

        session = self._new_session()
        response = session.send_message(prompt)
        return getattr(response, "text", "").strip()

    def stream_text(self, prompt: str) -> Iterable[str]:
        """以生成器回传 Gemini 的串流输出。"""
        if not prompt.strip():
            raise ValueError("输入内容不可为空白。")

        session = self._new_session()
        stream = session.send_message_stream(prompt)
        for chunk in stream:
            text_chunk = getattr(chunk, "text", "")
            if text_chunk:
                yield text_chunk


@lru_cache(maxsize=1)
def get_gemini_client() -> GeminiClient:
    """提供单例客户端，避免多次初始化 SDK。"""
    try:
        config = get_config()
        logger.info("正在初始化 Gemini 客户端 - 模型: %s", config.gemini_model)
        client = GeminiClient(api_key=config.gemini_api_key, model=config.gemini_model)
        logger.info("Gemini 客户端初始化成功")
        return client
    except GeminiClientError as exc:
        logger.error("Gemini 客户端初始化失败: %s", exc)
        raise
    except Exception as exc:
        logger.exception("初始化 Gemini 客户端时发生未预期的错误")
        raise GeminiClientError(f"初始化客户端时发生错误: {exc}") from exc


__all__ = ["GeminiClient", "GeminiClientError", "get_gemini_client"]

