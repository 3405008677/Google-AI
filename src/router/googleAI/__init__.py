"""
Google AI 路由模块

此包提供了与 Google Gemini AI 交互的 API 端点。
包含同步和流式聊天接口。
"""

from .api import router as google_ai_router

# 导出路由，使其可以被其他模块导入
__all__ = ["google_ai_router"]