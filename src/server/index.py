import os
import sys
import logging  # 这行代码导入了 Python 标准库中的 logging 模块，用于实现日志功能
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import mimetypes

from src.router.index import initRouter

# 配置日志
logging.basicConfig(
    # 设置日志级别为 INFO
    level=logging.INFO,
    # 定义日志的输出格式
    format="%(asctime)s - %(levelname)s - %(message)s",
    # 指定日志的输出目标，这里配置了两个处理器  将日志写入到名为 server.log 的文件中  将日志输出到控制台
    handlers=[
        logging.FileHandler(
            "server.log", encoding="utf-8"
        ),  # 文件处理器可以保留编码参数
        logging.StreamHandler(sys.stdout),  # 正确的方式创建 StreamHandler
    ],
)
# 创建一个日志记录器实例
logger = logging.getLogger(__name__)


# 添加MIME类型
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")
load_dotenv()


class Config:
    """配置管理类"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # 只在首次创建实例时加载配置
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        """加载配置"""
        self.port = int(os.getenv("PORT", 8080))
        self.host = os.getenv("HOST", "0.0.0.0")
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        self.static_dir = os.getenv("STATIC_DIR", "static")
        self.auth_token = os.getenv("AUTH_TOKEN")
        self.max_upload_size = int(os.getenv("MAX_UPLOAD_SIZE", 1024 * 1024))  # 默认1MB


app = FastAPI(title="Python Web Server", version="1.0.0")
config = Config()


# 创建静态文件目录
if not os.path.exists(config.static_dir):
    os.makedirs(config.static_dir)
    logger.info(f"创建静态文件目录: {config.static_dir}")

# 挂载静态文件路由
app.mount("/static", StaticFiles(directory=config.static_dir), name="static")


def initServer():

    import uvicorn

    initRouter(app)

    # 获取项目根目录
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    SSL_DIR = os.path.join(BASE_DIR, "SSL")
    SSL_CERT_FILE = os.path.join(SSL_DIR, "server.crt")
    SSL_KEY_FILE = os.path.join(SSL_DIR, "server.key")

    logger.info(f"🚀 服务器启动成功")
    logger.info(f"📍 地址: http://{config.host}:{config.port}")
    logger.info(f"🔧 调试模式: {config.debug}")
    logger.info(f"🔐 认证保护: {'启用' if config.auth_token else '禁用'}")
    logger.info(f"📁 静态文件目录: {config.static_dir}")
    logger.info(f"📦 最大上传大小: {config.max_upload_size} 字节")
    logger.info("=" * 50)
    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        log_level="info" if config.debug else "warning",
        ssl_certfile=SSL_CERT_FILE,
        ssl_keyfile=SSL_KEY_FILE,
    )


__all__ = ["initServer", "app"]
