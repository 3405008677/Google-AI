"""
意图分类器

使用 SelfHosted 模型判断用户意图，决定将任务分配给哪个服务。
"""
import json
import logging
from enum import Enum
from typing import Dict, List

from ...SelfHosted.models.self_hosted_client import get_self_hosted_client

logger = logging.getLogger(__name__)


class IntentType(str, Enum):
    """意图类型枚举"""
    CHAT = "chat"  # 普通聊天
    SEARCH = "search"  # 需要搜索网络信息
    DATABASE = "database"  # 需要查询数据库


class IntentClassifier:
    """意图分类器"""

    def __init__(self):
        self.client = get_self_hosted_client()
        self.system_prompt = """你是一个智能意图分类助手。根据用户的问题，判断用户的意图类型。

意图类型说明：
1. chat（普通聊天）：日常对话、问答、闲聊、情感交流等不需要外部信息的对话
2. search（网络搜索）：需要获取最新信息、实时数据、新闻、技术文档、产品信息等需要从网络搜索的内容
3. database（数据库查询）：明确提到查询数据库、查找记录、统计数据、业务数据等需要访问数据库的操作

请仔细分析用户的问题，只返回 JSON 格式的结果，不要添加任何其他文字说明。

返回格式：
{
  "intent": "chat|search|database",
  "confidence": 0.0-1.0,
  "reason": "简要说明判断理由"
}

示例：
用户："今天天气怎么样？"
返回：{"intent": "search", "confidence": 0.9, "reason": "需要获取实时天气信息"}

用户："你好，最近怎么样？"
返回：{"intent": "chat", "confidence": 0.95, "reason": "日常问候对话"}

用户："查询用户表中ID为123的记录"
返回：{"intent": "database", "confidence": 0.95, "reason": "明确要求查询数据库"}

用户："Python如何读取文件？"
返回：{"intent": "chat", "confidence": 0.8, "reason": "技术问答，可以使用已有知识回答"}

用户："最新的Python 3.12有什么新特性？"
返回：{"intent": "search", "confidence": 0.9, "reason": "需要获取最新版本信息"}"""

    async def classify(self, user_query: str) -> Dict:
        """
        分类用户意图
        
        Args:
            user_query: 用户查询
            
        Returns:
            Dict: 包含 intent, confidence, reason 的字典
        """
        try:
            messages = [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": user_query}
            ]
            
            # 调用模型进行意图分类
            response = self.client.generate_text(messages)
            
            # 尝试解析 JSON
            try:
                # 尝试提取 JSON（可能包含 markdown 代码块）
                if "```json" in response:
                    json_str = response.split("```json")[1].split("```")[0].strip()
                elif "```" in response:
                    json_str = response.split("```")[1].split("```")[0].strip()
                else:
                    json_str = response.strip()
                
                result = json.loads(json_str)
                
                # 验证结果格式
                if "intent" not in result:
                    raise ValueError("Missing 'intent' field")
                
                # 确保 intent 是有效的
                intent = result["intent"].lower()
                if intent not in [e.value for e in IntentType]:
                    logger.warning(f"Invalid intent: {intent}, defaulting to chat")
                    intent = IntentType.CHAT.value
                
                result["intent"] = intent
                result["confidence"] = result.get("confidence", 0.5)
                result["reason"] = result.get("reason", "")
                
                logger.info(f"Intent classified: {intent} (confidence: {result['confidence']})")
                return result
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON from model response: {response}, error: {e}")
                # 如果解析失败，尝试从文本中提取意图关键词
                return self._fallback_classify(user_query)
                
        except Exception as e:
            logger.error(f"Intent classification failed: {e}", exc_info=True)
            # 发生错误时，使用备用分类方法
            return self._fallback_classify(user_query)

    def _fallback_classify(self, query: str) -> Dict:
        """
        备用分类方法（基于关键词）
        
        Args:
            query: 用户查询
            
        Returns:
            Dict: 分类结果
        """
        query_lower = query.lower()
        
        # 数据库相关关键词
        db_keywords = ["查询", "数据库", "表", "记录", "select", "where", "sql", "数据表", "统计"]
        if any(keyword in query_lower for keyword in db_keywords):
            return {
                "intent": IntentType.DATABASE.value,
                "confidence": 0.7,
                "reason": "检测到数据库相关关键词"
            }
        
        # 搜索相关关键词
        search_keywords = ["最新", "最近", "现在", "当前", "实时", "新闻", "搜索", "查找", "找", "查"]
        if any(keyword in query_lower for keyword in search_keywords):
            return {
                "intent": IntentType.SEARCH.value,
                "confidence": 0.7,
                "reason": "检测到搜索相关关键词"
            }
        
        # 默认返回聊天
        return {
            "intent": IntentType.CHAT.value,
            "confidence": 0.6,
            "reason": "默认分类为普通聊天"
        }

