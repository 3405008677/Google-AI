import sys
import os

from src.config import get_config, get_local_ip
from src.server import initServer

# 将项目根目录加入 sys.path，确保相对导入能正常运作
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if root_dir not in sys.path:
    # 放到 sys.path 前面以保证优先使用工程内模块
    sys.path.insert(0, root_dir)

"""
启动服务
    1. 获取配置
    2. 获取本机 IP
    3. 打印访问地址信息
    4. 启动服务
"""
if __name__ == "__main__":
    # 获取配置
    config = get_config()

    # 获取本机 IP（在服务器启动前）
    local_ip = get_local_ip()

    # 打印访问地址信息
    protocol = "https" if config.ssl_enabled else "http"
    print(f"\n{'=' * 50}")
    print("🌐 服务访问地址:")
    print(f"   本地访问: {protocol}://127.0.0.0:{config.port}")
    if local_ip != "127.0.0.0":
        print(f"   局域网访问: {protocol}://{local_ip}:{config.port}")
    print(f"{'=' * 50}\n")

    # 主入口：启动 FastAPI/Uvicorn 服务（阻塞运行）
    initServer()
