"""
速通优化层 (Performance Layer)

在调用昂贵的 LLM 之前，先过两道"筛子"：
1. 语义缓存 (Semantic Cache)：使用 Redis 向量存储，相似度 > 0.95 直接返回缓存
2. 规则引擎 (Rule Engine)：处理非推理类指令，基于关键词或正则匹配
"""

import os
import re
import json
import hashlib
from typing import Optional, Dict, Any, List, Tuple
from functools import lru_cache

import numpy as np
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

try:
    import redis
    from sentence_transformers import SentenceTransformer
    REDIS_AVAILABLE = True
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    SENTENCE_TRANSFORMERS_AVAILABLE = False

from src.server.logging_setup import logger


class SemanticCache:
    """
    语义缓存模块
    
    使用 Redis 向量存储，将用户 Query 向量化，如果与缓存中的 Query 相似度 > 0.95，
    直接返回上次的 Answer。耗时 0ms，费用 0 元。
    """

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_db: int = 0,
        redis_password: Optional[str] = None,
        similarity_threshold: float = 0.95,
        cache_prefix: str = "semantic_cache:",
        enable_cache: bool = True,
    ):
        """
        初始化语义缓存

        Args:
            redis_host: Redis 主机地址
            redis_port: Redis 端口
            redis_db: Redis 数据库编号
            redis_password: Redis 密码（可选）
            similarity_threshold: 相似度阈值，默认 0.95
            cache_prefix: Redis key 前缀
            enable_cache: 是否启用缓存
        """
        self.similarity_threshold = similarity_threshold
        self.cache_prefix = cache_prefix
        self.enable_cache = enable_cache and REDIS_AVAILABLE

        # 初始化 Redis 客户端
        self.redis_client = None
        if self.enable_cache:
            try:
                self.redis_client = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    password=redis_password,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                )
                # 测试连接
                self.redis_client.ping()
                logger.info("语义缓存：Redis 连接成功")
            except Exception as e:
                logger.warning(f"语义缓存：Redis 连接失败，将禁用缓存: {e}")
                self.enable_cache = False
                self.redis_client = None

        # 初始化向量化模型
        self.embedding_model = None
        if self.enable_cache and SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                # 使用轻量级的中文模型
                model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
                self.embedding_model = SentenceTransformer(model_name)
                logger.info(f"语义缓存：向量化模型加载成功 ({model_name})")
            except Exception as e:
                logger.warning(f"语义缓存：向量化模型加载失败，将禁用缓存: {e}")
                self.enable_cache = False
                self.embedding_model = None

    def _get_embedding(self, text: str) -> Optional[np.ndarray]:
        """
        获取文本的向量表示

        Args:
            text: 输入文本

        Returns:
            向量数组，如果失败返回 None
        """
        if not self.embedding_model:
            return None

        try:
            embedding = self.embedding_model.encode(text, normalize_embeddings=True)
            return embedding
        except Exception as e:
            logger.error(f"语义缓存：向量化失败: {e}")
            return None

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        计算余弦相似度

        Args:
            vec1: 向量1
            vec2: 向量2

        Returns:
            相似度值（0-1）
        """
        return float(np.dot(vec1, vec2))

    def _get_cache_key(self, query_hash: str) -> str:
        """生成缓存 key"""
        return f"{self.cache_prefix}query:{query_hash}"

    def _get_vector_key(self, query_hash: str) -> str:
        """生成向量存储 key"""
        return f"{self.cache_prefix}vector:{query_hash}"

    def get(self, query: str) -> Optional[Dict[str, Any]]:
        """
        从缓存中获取答案

        Args:
            query: 用户查询

        Returns:
            如果找到相似缓存，返回 {"answer": ..., "query": ..., "similarity": ...}，否则返回 None
        """
        if not self.enable_cache or not self.redis_client or not self.embedding_model:
            return None

        try:
            # 获取查询向量
            query_embedding = self._get_embedding(query)
            if query_embedding is None:
                return None

            # 获取所有缓存的查询向量
            pattern = f"{self.cache_prefix}vector:*"
            vector_keys = self.redis_client.keys(pattern)

            best_match = None
            best_similarity = 0.0

            for vector_key in vector_keys:
                try:
                    # 从 Redis 获取缓存的向量（存储为 JSON）
                    cached_vector_json = self.redis_client.get(vector_key)
                    if not cached_vector_json:
                        continue

                    cached_vector = np.array(json.loads(cached_vector_json))
                    similarity = self._cosine_similarity(query_embedding, cached_vector)

                    if similarity > best_similarity:
                        best_similarity = similarity
                        # 提取 query_hash
                        query_hash = vector_key.replace(f"{self.cache_prefix}vector:", "")
                        best_match = query_hash

                except Exception as e:
                    logger.debug(f"语义缓存：处理缓存向量时出错: {e}")
                    continue

            # 如果找到相似度超过阈值的匹配
            if best_match and best_similarity >= self.similarity_threshold:
                cache_key = self._get_cache_key(best_match)
                cached_data = self.redis_client.get(cache_key)
                if cached_data:
                    result = json.loads(cached_data)
                    result["similarity"] = best_similarity
                    logger.info(
                        f"语义缓存命中 | 相似度: {best_similarity:.4f} | 查询: {query[:50]}..."
                    )
                    return result

        except Exception as e:
            logger.error(f"语义缓存：获取缓存时出错: {e}")

        return None

    def set(self, query: str, answer: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        将查询和答案存入缓存

        Args:
            query: 用户查询
            answer: 答案
            metadata: 可选的元数据

        Returns:
            是否成功存储
        """
        if not self.enable_cache or not self.redis_client or not self.embedding_model:
            return False

        try:
            # 生成查询的 hash（用于去重）
            query_hash = hashlib.md5(query.encode("utf-8")).hexdigest()

            # 获取查询向量
            query_embedding = self._get_embedding(query)
            if query_embedding is None:
                return False

            # 存储向量
            vector_key = self._get_vector_key(query_hash)
            self.redis_client.set(
                vector_key,
                json.dumps(query_embedding.tolist()),
                ex=86400 * 7,  # 7 天过期
            )

            # 存储答案和元数据
            cache_key = self._get_cache_key(query_hash)
            cache_data = {
                "query": query,
                "answer": answer,
                "metadata": metadata or {},
            }
            self.redis_client.set(
                cache_key,
                json.dumps(cache_data, ensure_ascii=False),
                ex=86400 * 7,  # 7 天过期
            )

            logger.debug(f"语义缓存：已存储查询和答案 | 查询: {query[:50]}...")
            return True

        except Exception as e:
            logger.error(f"语义缓存：存储缓存时出错: {e}")
            return False


class RuleEngine:
    """
    规则引擎模块
    
    处理"你好"、"你是谁"、"清除历史"等非推理类指令。
    基于关键词或正则匹配，匹配成功直接返回预设话术，不进入 Agent 流程。
    """

    def __init__(self, enable_engine: bool = True):
        """
        初始化规则引擎

        Args:
            enable_engine: 是否启用规则引擎
        """
        self.enable_engine = enable_engine
        self.rules: List[Tuple[str, str, str]] = []  # [(pattern, answer, rule_type), ...]
        self._load_default_rules()

    def _load_default_rules(self):
        """加载默认规则"""
        default_rules = [
            # (pattern, answer, rule_type)
            (r"^(你好|hello|hi|您好|早上好|下午好|晚上好)[\s!！。，,]*$", "你好！我是 AI 助手，有什么可以帮助你的吗？", "greeting"),
            (r"^(你是谁|你叫什么|介绍.*自己|what.*your.*name|who.*are.*you)[\s!！。，,]*$", "我是一个 AI 助手，可以帮助你回答问题、处理任务等。", "identity"),
            (r"^(清除.*历史|清空.*历史|删除.*历史|clear.*history|reset.*history)[\s!！。，,]*$", "好的，已清除历史记录。", "clear_history"),
            (r"^(谢谢|感谢|thank.*you|thanks)[\s!！。，,]*$", "不客气！很高兴能帮助你。", "thanks"),
            (r"^(再见|拜拜|bye|goodbye|see.*you)[\s!！。，,]*$", "再见！祝你一切顺利。", "goodbye"),
            (r"^(帮助|help|如何使用|怎么用)[\s!！。，,]*$", "我可以帮助你回答问题、处理任务等。请告诉我你需要什么帮助。", "help"),
        ]

        for pattern, answer, rule_type in default_rules:
            self.add_rule(pattern, answer, rule_type)

    def add_rule(self, pattern: str, answer: str, rule_type: str = "custom"):
        """
        添加规则

        Args:
            pattern: 正则表达式模式或关键词
            answer: 匹配成功时返回的答案
            rule_type: 规则类型（用于分类和调试）
        """
        self.rules.append((pattern, answer, rule_type))
        logger.debug(f"规则引擎：已添加规则 | 类型: {rule_type} | 模式: {pattern[:50]}")

    def match(self, query: str) -> Optional[Dict[str, Any]]:
        """
        匹配查询

        Args:
            query: 用户查询

        Returns:
            如果匹配成功，返回 {"answer": ..., "rule_type": ...}，否则返回 None
        """
        if not self.enable_engine:
            return None

        # 清理查询（去除首尾空格，转为小写）
        cleaned_query = query.strip().lower()

        for pattern, answer, rule_type in self.rules:
            try:
                # 使用正则匹配
                if re.search(pattern, cleaned_query, re.IGNORECASE):
                    logger.info(f"规则引擎命中 | 类型: {rule_type} | 查询: {query[:50]}...")
                    return {
                        "answer": answer,
                        "rule_type": rule_type,
                        "pattern": pattern,
                    }
            except Exception as e:
                logger.warning(f"规则引擎：规则匹配时出错 | 模式: {pattern} | 错误: {e}")
                continue

        return None


class PerformanceLayerMiddleware(BaseHTTPMiddleware):
    """
    速通优化层中间件
    
    在调用昂贵的 LLM 之前，先过两道"筛子"：
    1. 规则引擎：处理非推理类指令
    2. 语义缓存：返回相似查询的缓存答案
    """

    def __init__(
        self,
        app: ASGIApp,
        enable_performance_layer: bool = True,
        enable_semantic_cache: bool = True,
        enable_rule_engine: bool = True,
        skip_paths: Optional[List[str]] = None,
        **kwargs,
    ):
        """
        初始化速通优化层中间件

        Args:
            app: FastAPI 应用实例
            enable_performance_layer: 是否启用速通优化层
            enable_semantic_cache: 是否启用语义缓存
            enable_rule_engine: 是否启用规则引擎
            skip_paths: 需要跳过优化的路径列表
            **kwargs: 传递给 SemanticCache 和 RuleEngine 的其他参数
        """
        super().__init__(app)
        self.enable_performance_layer = enable_performance_layer
        self.skip_paths = [path.rstrip("/") or "/" for path in (skip_paths or [])]

        # 初始化语义缓存
        self.semantic_cache = None
        if enable_semantic_cache and enable_performance_layer:
            redis_host = os.getenv("REDIS_HOST", "localhost")
            redis_port = int(os.getenv("REDIS_PORT", "6379"))
            redis_db = int(os.getenv("REDIS_DB", "0"))
            redis_password = os.getenv("REDIS_PASSWORD")
            similarity_threshold = float(os.getenv("SEMANTIC_CACHE_THRESHOLD", "0.95"))

            self.semantic_cache = SemanticCache(
                redis_host=redis_host,
                redis_port=redis_port,
                redis_db=redis_db,
                redis_password=redis_password,
                similarity_threshold=similarity_threshold,
                enable_cache=enable_semantic_cache,
            )

        # 初始化规则引擎
        self.rule_engine = None
        if enable_rule_engine and enable_performance_layer:
            self.rule_engine = RuleEngine(enable_engine=enable_rule_engine)

    def _match_skip_path(self, path: str) -> bool:
        """检查路径是否应该跳过优化"""
        normalized_path = path.rstrip("/") or "/"
        for rule in self.skip_paths:
            if normalized_path == rule:
                return True
            if normalized_path.startswith(f"{rule}/"):
                return True
        return False

    def _extract_query_from_request(self, request: Request) -> Optional[str]:
        """
        从请求中提取查询文本

        支持从请求体（JSON）中提取 query、message、prompt 等字段
        """
        # 这里需要异步读取请求体，但中间件中无法直接读取
        # 实际使用时，应该在路由处理函数中调用
        # 这里返回 None，表示需要从路由中获取
        return None

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        处理请求并应用速通优化层

        注意：由于 FastAPI 中间件无法直接读取请求体（需要 await request.body()），
        实际的查询提取和缓存逻辑应该在路由处理函数中调用 PerformanceLayer 的方法。
        这里主要做路径检查和准备。
        """
        # 如果未启用优化层，直接放行
        if not self.enable_performance_layer:
            return await call_next(request)

        # 检查是否需要跳过优化
        if self._match_skip_path(request.url.path):
            return await call_next(request)

        # 继续处理请求
        # 实际的语义缓存和规则引擎检查应该在路由处理函数中进行
        response = await call_next(request)

        return response


class PerformanceLayer:
    """
    速通优化层主类
    
    提供便捷的方法供路由处理函数调用
    """

    def __init__(
        self,
        enable_semantic_cache: bool = True,
        enable_rule_engine: bool = True,
        **kwargs,
    ):
        """
        初始化速通优化层

        Args:
            enable_semantic_cache: 是否启用语义缓存
            enable_rule_engine: 是否启用规则引擎
            **kwargs: 传递给 SemanticCache 和 RuleEngine 的其他参数
        """
        # 初始化语义缓存
        self.semantic_cache = None
        if enable_semantic_cache:
            redis_host = os.getenv("REDIS_HOST", "localhost")
            redis_port = int(os.getenv("REDIS_PORT", "6379"))
            redis_db = int(os.getenv("REDIS_DB", "0"))
            redis_password = os.getenv("REDIS_PASSWORD")
            similarity_threshold = float(os.getenv("SEMANTIC_CACHE_THRESHOLD", "0.95"))

            self.semantic_cache = SemanticCache(
                redis_host=redis_host,
                redis_port=redis_port,
                redis_db=redis_db,
                redis_password=redis_password,
                similarity_threshold=similarity_threshold,
                enable_cache=enable_semantic_cache,
            )

        # 初始化规则引擎
        self.rule_engine = None
        if enable_rule_engine:
            self.rule_engine = RuleEngine(enable_engine=enable_rule_engine)

    def process_query(self, query: str) -> Optional[Dict[str, Any]]:
        """
        处理查询，依次检查规则引擎和语义缓存

        Args:
            query: 用户查询

        Returns:
            如果命中规则或缓存，返回 {"answer": ..., "source": "rule_engine"|"semantic_cache", ...}
            否则返回 None，表示需要继续处理（调用 LLM）
        """
        # 1. 先检查规则引擎
        if self.rule_engine:
            rule_result = self.rule_engine.match(query)
            if rule_result:
                return {
                    "answer": rule_result["answer"],
                    "source": "rule_engine",
                    "rule_type": rule_result.get("rule_type"),
                }

        # 2. 再检查语义缓存
        if self.semantic_cache:
            cache_result = self.semantic_cache.get(query)
            if cache_result:
                return {
                    "answer": cache_result["answer"],
                    "source": "semantic_cache",
                    "similarity": cache_result.get("similarity"),
                    "cached_query": cache_result.get("query"),
                }

        # 3. 都没有命中，返回 None，表示需要调用 LLM
        return None

    def cache_answer(self, query: str, answer: str, metadata: Optional[Dict[str, Any]] = None):
        """
        将查询和答案存入语义缓存

        Args:
            query: 用户查询
            answer: LLM 生成的答案
            metadata: 可选的元数据
        """
        if self.semantic_cache:
            self.semantic_cache.set(query, answer, metadata)


# 全局单例实例
_performance_layer_instance: Optional[PerformanceLayer] = None


def get_performance_layer() -> PerformanceLayer:
    """获取全局 PerformanceLayer 单例实例"""
    global _performance_layer_instance
    if _performance_layer_instance is None:
        enable_semantic_cache = os.getenv("ENABLE_SEMANTIC_CACHE", "true").lower() in ("true", "1", "yes")
        enable_rule_engine = os.getenv("ENABLE_RULE_ENGINE", "true").lower() in ("true", "1", "yes")
        _performance_layer_instance = PerformanceLayer(
            enable_semantic_cache=enable_semantic_cache,
            enable_rule_engine=enable_rule_engine,
        )
    return _performance_layer_instance


def register_performance_layer_middleware(
    app,
    enable_performance_layer: bool = True,
    enable_semantic_cache: bool = True,
    enable_rule_engine: bool = True,
    skip_paths: Optional[List[str]] = None,
) -> None:
    """
    注册速通优化层中间件到 FastAPI 应用

    Args:
        app: FastAPI 应用实例
        enable_performance_layer: 是否启用速通优化层
        enable_semantic_cache: 是否启用语义缓存
        enable_rule_engine: 是否启用规则引擎
        skip_paths: 需要跳过优化的路径列表
    """
    app.add_middleware(
        PerformanceLayerMiddleware,
        enable_performance_layer=enable_performance_layer,
        enable_semantic_cache=enable_semantic_cache,
        enable_rule_engine=enable_rule_engine,
        skip_paths=skip_paths,
    )


__all__ = [
    "SemanticCache",
    "RuleEngine",
    "PerformanceLayer",
    "PerformanceLayerMiddleware",
    "get_performance_layer",
    "register_performance_layer_middleware",
]

