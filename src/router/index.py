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

from .AI.googleAI.api import initGoogleAI  # 导入 Google AI 路由初始化函数
from .AI.Bailian.api import initBailian  # 导入阿里云百炼路由初始化函数
from .AI.SelfHosted.api import initSelfHosted  # 导入自建模型路由初始化函数
from .AI.Tavily.api import initTavily  # 导入 Tavily 搜索路由初始化函数
from .AI.Orchestrator.api import initOrchestrator  # 导入全能调度系统路由初始化函数

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
    initGoogleAI(app, prefix="/GoogleAI")

    # 注册阿里云百炼路由
    initBailian(app, prefix="/Bailian")

    # 注册自建模型路由
    initSelfHosted(app, prefix="/SelfHosted")

    # 注册 Tavily 搜索路由
    initTavily(app, prefix="/Tavily")

    # 注册全能调度系统路由
    initOrchestrator(app, prefix="/Orchestrator")


# 定义模块的公共接口
# 当其他模块使用 from src.router.index import * 时，只会导入此处列出的内容
# 这有助于控制模块的对外接口，避免导入不必要的内部实现
__all__ = ["initRouter"]
