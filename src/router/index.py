"""
路由模块主入口文件

此模块负责：
1. 定义主路由器和基础 API 端点
2. 注册所有子路由模块（如 Google AI 路由）
3. 提供统一的 API 前缀管理
"""

import logging
from fastapi.responses import StreamingResponse

from fastapi import APIRouter  # 导入 FastAPI 路由器，用于定义路由端点

from .googleAI.api import initGoogleAI  # 导入 Google AI 路由初始化函数

# 创建主路由器实例
# 此路由器用于定义应用程序的主要 API 端点
router = APIRouter()


@router.post("/Home")  # 注册 POST 方法的 /home 端点
def helloHome():
    logging.info("Hello Home")
    return StreamingResponse(
        content="你好", media_type="text/plain"
    )  # 返回简单的欢迎消息


def initRouter(app):
    # 注册主路由
    app.include_router(router, prefix="")

    # 注册 Google AI 路由
    initGoogleAI(app, prefix="")


# 定义模块的公共接口
# 当其他模块使用 from src.router.index import * 时，只会导入此处列出的内容
# 这有助于控制模块的对外接口，避免导入不必要的内部实现
__all__ = ["initRouter"]
