from fastapi import APIRouter
from .googleAI.index import initGoogleAI

router = APIRouter()


@router.get("/home")
def helloHome():
    return {"message": "你好"}


# 初始化路由
def initRouter(app):
    # 创建通过路由
    app.include_router(router, prefix="/api")
    # 创建 谷歌AI webSocket
    initGoogleAI(app)


__all__ = ["initRouter"]
