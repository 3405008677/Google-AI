import os
from typing import Optional  # 添加必要的类型导入
from fastapi import APIRouter, HTTPException
from dotenv import load_dotenv
from google import genai
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel


class GeminiAI:
    """Gemini AI 客户端封装类"""

    # 初始化 谷歌 AI
    def __init__(self, api_key: Optional[str] = None):
        # 加载环境变量
        load_dotenv()

        # 获取API密钥
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        # 如果没有 key 则退出
        if not self.api_key:
            raise ValueError("API密钥未提供")

        # 创建客户端实例
        try:
            self.GeminiAI = genai.Client(api_key=self.api_key).chats.create(
                model="gemini-2.5-flash"
            )
            print("🤖 Gemini AI 客户端已启动")
            print("=" * 50)
        except Exception as e:
            print(f"❌ 程序启动失败: {e}")
            raise ConnectionError(f"无法连接到Gemini API: {e}")

    # AI交流
    def comminicate(self, text: str, stream: bool = True):
        # text: 输入文本
        # stream: 是否使用流式输出
        if not text.strip():
            return ValueError("输入文本不能为空")

        try:
            if stream:
                return self.generate_content_response(text=text)
            else:
                return self.generate_content(text=text)
        except Exception as e:
            raise RuntimeError(f"生成内容时发生错误: {e}")

    # 普通响应  """同步生成内容"""
    async def generate_content(self, text: str):
        try:
            # 生成内容
            response = self.GeminiAI.send_message(text)
            return response.text
        except Exception as e:
            raise RuntimeError(f"生成内容时发生错误: {e}")

    # 流式响应
    async def generate_content_response(self, text: str):

        try:
            response = self.GeminiAI.send_message_stream(text)
            for chunk in response:
                yield chunk.text + "\n"
        except Exception as e:
            print(f"\n流式输出中断: {e}")


# 创建子路由，指定前缀和标签
router = APIRouter(
    prefix="/GoogleAI",  # 添加前缀
    tags=["GoogleAI"],  # 用于API文档分组
    responses={404: {"description": "Not found"}},  # 公共响应
)


# 创建AI客户端
ai_client = GeminiAI()


# 创建异步生成器包装器
async def response_generator(ai, text):
    try:
        # 使用异步迭代器处理流
        async for chunk in ai.comminicate(text=text):
            # 确保每个数据块都是字符串
            print(f"流式输出: {chunk}")
            # import asyncio
            # await asyncio.sleep(2)
            yield str(chunk)
    except Exception as e:
        # 捕获并发送最终错误
        print(f"流式输出捕获并发送最终错误: {e}")
        yield f"[FATAL ERROR] {str(e)}"


class Params_TYPE(BaseModel):
    text: str


@router.post("/ContentResponse")
async def GoogleAI_Content_Response(params: Params_TYPE):
    # 检查参数中是否有 text 字段
    if not params.text.strip():  # 验证文本不为空
        raise HTTPException(status_code=400, detail="请求中缺少 'text' 字段或内容为空")

    text_content = params.text
    print(f"收到消息: {text_content}")

    # 使用正确的参数传递
    return StreamingResponse(
        response_generator(ai=ai_client, text=text_content),
        media_type="text/event-stream",  # 更适合流式传输的媒体类型
    )


def initGoogleAI(app):
    app.include_router(router)


__all__ = ["initGoogleAI"]
