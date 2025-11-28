from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Iterable

from openai import OpenAI

logger = logging.getLogger(__name__)


class BailianClientError(RuntimeError):
    """阿里云百炼客户端错误"""


class BailianClient:
    """阿里云百炼文本生成客户端

    通过 OpenAI 兼容模式调用百炼的对话接口：
    - 同步：生成完整回复
    - 流式：逐块产出回复内容
    """

    def __init__(self, model: str = "qwen-plus"):
        api_key = os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise BailianClientError("尚未提供 DASHSCOPE_API_KEY，无法调用阿里云百炼接口。")

        self._model = model
        try:
            self._client = OpenAI(
                api_key=api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
        except Exception as exc:  # pragma: no cover - SDK 初始化错误直接冒泡
            raise BailianClientError(f"初始化 Bailian OpenAI 客户端失败: {exc}") from exc

    def generate_text(self, prompt: str) -> str:
        """调用百炼，同步生成整段回复。"""
        if not prompt.strip():
            raise ValueError("输入内容不可为空白。")

        try:
            completion = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
                stream=False,  # 同步返回完整回复
            )
        except Exception as exc:
            logger.error("调用百炼同步接口失败: %s", exc)
            raise BailianClientError(f"调用百炼同步接口失败: {exc}") from exc

        try:
            message = completion.choices[0].message
            return (message.content or "").strip()
        except Exception as exc:  # 结构异常
            logger.error("解析百炼同步响应失败: %s", exc)
            raise BailianClientError(f"解析百炼同步响应失败: {exc}") from exc

    def stream_text(self, prompt: str) -> Iterable[str]:
        """以生成器形式调用百炼流式输出。"""
        if not prompt.strip():
            raise ValueError("输入内容不可为空白。")

        try:
            completion = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
                stream=True,  # 流式返回回复
                stream_options={"include_usage": True},
            )
        except Exception as exc:
            logger.error("调用百炼流式接口失败: %s", exc)
            raise BailianClientError(f"调用百炼流式接口失败: {exc}") from exc

        for chunk in completion:
            try:
                # 检查 chunk 是否有 choices 且不为空
                if not hasattr(chunk, "choices") or not chunk.choices:
                    continue

                # OpenAI 兼容协议下，内容通常在 choices[0].delta.content 或 choices[0].message.content
                choice = chunk.choices[0]
                delta = getattr(choice, "delta", None)
                if delta is not None:
                    text = delta.content or ""
                else:
                    # 兼容部分实现可能直接放在 message.content
                    message = getattr(choice, "message", None)
                    text = getattr(message, "content", "") if message else ""

                if text:
                    yield text
            except (IndexError, AttributeError) as exc:
                # 单块解析失败不应中断整个流，静默跳过异常 chunk
                logger.debug("跳过无效的流式响应分片: %s", exc)
                continue
            except Exception as exc:  # 其他异常记录错误但继续处理
                logger.error("解析百炼流式响应分片失败: %s", exc)
                continue


@lru_cache(maxsize=1)
def get_bailian_client() -> BailianClient:
    """提供单例百炼客户端。"""
    logger.info("正在初始化 Bailian 客户端（阿里云百炼 OpenAI 兼容模式）")
    return BailianClient()


__all__ = ["BailianClient", "BailianClientError", "get_bailian_client"]
