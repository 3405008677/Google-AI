import os
import json
from typing import Optional
from dotenv import load_dotenv
from google import genai
from google.genai import types
from fastapi import WebSocket, WebSocketDisconnect


class GeminiAI:
    """Gemini AI 客户端封装类"""

    # 初始化 谷歌 AI
    def __init__(self, websocket: WebSocket, api_key: Optional[str] = None):
        # 加载环境变量
        load_dotenv()

        self.websocket = websocket

        # 获取API密钥
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        # 如果没有 key 则退出
        if not self.api_key:
            raise ValueError(
                "API密钥未提供，请设置GEMINI_API_KEY环境变量或在初始化时传入"
            )

        # 创建客户端实例
        try:
            self.GeminiAI = genai.Client(api_key=self.api_key)
            print("🤖 Gemini AI 客户端已启动")
            print("=" * 50)
        except Exception as e:
            print(f"❌ 程序启动失败: {e}")
            raise ConnectionError(f"无法连接到Gemini API: {e}")

    # AI交流
    async def comminicate(
        self,
        text: str,
        model: str = "gemini-2.5-flash",
        stream: bool = True,
        type: str = "1",
        thinking_budget: int = 0,
    ):
        # text: 输入文本
        # model: 使用的模型名称
        # stream: 是否使用流式输出
        # type: 模型类型
        # thinking_budget: 思考预算
        if not text.strip():
            return ValueError("输入文本不能为空")

        try:
            config = types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget)
            )

            if stream:
                await self.generate_content_response(
                    text=text, model=model, config=config
                )
            else:
                await self.generate_content(text=text, model=model, config=config)
        except Exception as e:
            raise RuntimeError(f"生成内容时发生错误: {e}")

    # 普通响应  """同步生成内容"""
    async def generate_content(self, text: str, model: str, config):
        try:

            # 生成内容
            response = self.GeminiAI.models.generate_content(
                contents=text, model=model, config=config
            )

            json_data = json.dumps({"type": "generate_content", "text": response.text})

            await self.websocket.send_text(json_data)

        except Exception as e:
            raise RuntimeError(f"生成内容时发生错误: {e}")

    # 流式响应
    async def generate_content_response(self, text: str, model: str, config):

        try:
            text = [text]
            response = self.GeminiAI.models.generate_content_stream(
                contents=text, model=model, config=config
            )

            for chunk in response:
                json_data = json.dumps({"type": "generate_content", "text": chunk.text})
                print(chunk.text, end="")
                await self.websocket.send_text(json_data)

        except Exception as e:
            print(f"\n流式输出中断: {e}")


# 存储所有连接的客户端
active_connections = []


def initGoogleAI(app):
    print("创建 谷歌AI Websocket")

    @app.websocket("/GoogleAI")
    async def websocket_init_google(websocket: WebSocket):
        await websocket.accept()
        # 将新连接加入列表
        active_connections.append(websocket)
        client = websocket.client
        print("客户端连接 GoogleAI")

        # 创建AI客户端
        ai_client = GeminiAI(websocket)

        try:
            while True:
                data = await websocket.receive_text()
                print(f"收到消息: {data}")

                print(f"等待AI回复")
                await ai_client.comminicate(text=data, model="gemini-2.5-flash")
                print(f"回复成功")

        except WebSocketDisconnect:
            # 客户端断开连接时移除
            active_connections.remove(websocket)
        except Exception as e:
            print(f"GoogleAI 连接错误: {e}")
        finally:
            # 确保连接关闭
            await websocket.close()
            print(f"客户端断开连接 GoogleAI: {client.host}:{client.port}")


__all__ = ["initGoogleAI"]
