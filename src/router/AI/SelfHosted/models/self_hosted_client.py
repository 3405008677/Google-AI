from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Dict, Iterable, List

from openai import OpenAI

logger = logging.getLogger(__name__)


class SelfHostedClientError(RuntimeError):
    """自建模型客户端错误"""


class SelfHostedClient:
    """自建模型文本生成客户端（OpenAI 兼容协议）"""

    def __init__(self, model: str | None = None):
        base_url = os.getenv("SELF_MODEL_BASE_URL", "https://ai.pengqianjing.top/v1").rstrip("/")
        if not base_url:
            raise SelfHostedClientError("SELF_MODEL_BASE_URL 未配置，无法连接自建模型。")

        api_key = os.getenv("SELF_MODEL_API_KEY")
        if not api_key:
            # 某些开源部署可能不校验密钥，此处允许占位符继续执行
            api_key = "EMPTY_KEY"
            logger.warning("SELF_MODEL_API_KEY 未设置，使用占位符发起请求。")

        self._model = model or os.getenv("SELF_MODEL_NAME")
        if not self._model:
            raise SelfHostedClientError("尚未配置模型名称，请通过构造参数或 SELF_MODEL_NAME 指定。")

        logger.info("Initialising SelfHosted client with model `%s`", self._model)
        try:
            self._client = OpenAI(
                api_key=api_key,
                base_url=base_url,
                default_headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                },
            )
        except Exception as exc:  # pragma: no cover
            raise SelfHostedClientError(f"初始化自建模型 OpenAI 客户端失败: {exc}") from exc

    def generate_text(self, messages: List[Dict[str, str]]) -> str:
        if not messages:
            raise ValueError("messages 不能为空。")

        try:
            completion = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                stream=False,
            )
        except Exception as exc:
            logger.error("调用自建模型同步接口失败: %s", exc)
            raise SelfHostedClientError(f"调用自建模型同步接口失败: {exc}") from exc

        try:
            message = completion.choices[0].message
            return (message.content or "").strip()
        except Exception as exc:
            logger.error("解析自建模型同步响应失败: %s", exc)
            raise SelfHostedClientError(f"解析自建模型同步响应失败: {exc}") from exc

    def stream_text(self, messages: List[Dict[str, str]]) -> Iterable[str]:
        if not messages:
            raise ValueError("messages 不能为空。")

        try:
            completion = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                stream=True,
                # stream_options={"include_usage": True},
            )
        except Exception as exc:
            logger.error("调用自建模型流式接口失败: %s", exc)
            raise SelfHostedClientError(f"调用自建模型流式接口失败: {exc}") from exc

        try:
            for chunk in completion:
                try:
                    if not hasattr(chunk, "choices") or not chunk.choices:
                        continue

                    choice = chunk.choices[0]
                    delta = getattr(choice, "delta", None)
                    if delta is not None:
                        text = delta.content or ""
                    else:
                        message = getattr(choice, "message", None)
                        text = getattr(message, "content", "") if message else ""

                    if text:
                        yield text
                except (IndexError, AttributeError) as exc:
                    logger.debug("跳过无效的流式响应分片: %s", exc)
                    continue
                except Exception as exc:
                    logger.error("解析自建模型流式响应分片失败: %s", exc)
                    continue
        except (ConnectionError, BrokenPipeError) as exc:
            # 连接中断，记录警告但允许继续（可能已经收到部分数据）
            logger.warning("流式连接中断，可能已收到部分数据: %s", exc)
            # 不重新抛出异常，让调用者处理已收到的数据
        except Exception as exc:
            # 其他异常重新抛出
            logger.error("流式响应过程中发生错误: %s", exc)
            raise


@lru_cache(maxsize=1)
def get_self_hosted_client() -> SelfHostedClient:
    logger.info("正在初始化自建模型客户端（OpenAI 兼容模式）")
    return SelfHostedClient()


__all__ = ["SelfHostedClient", "SelfHostedClientError", "get_self_hosted_client"]

