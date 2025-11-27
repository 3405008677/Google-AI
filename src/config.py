import os  # 操作系统接口，用于读取环境变量
import socket  # 网络套接字，用于获取本机 IP 地址
from dataclasses import dataclass  # 数据类装饰器，用于创建配置类
from functools import lru_cache  # 缓存装饰器，用于单例模式
from pathlib import Path  # 路径处理，用于文件路径操作

from dotenv import load_dotenv  # 加载 .env 文件中的环境变量

# 预先载入 .env，确保后续读取环境变量时皆已就绪
load_dotenv()  # 从 .env 文件加载环境变量到 os.environ


def _as_bool(value: str | None, default: bool = False) -> bool:  # 将字符串转换为布尔值的辅助函数
    """将常见字串值转为布林，未提供时套用预设值。"""
    if value is None:  # 如果值为 None
        return default  # 返回默认值
    return value.strip().lower() in {"1", "true", "yes", "on"}  # 去除空白并转为小写，检查是否为真值


@dataclass(frozen=True)  # 使用数据类装饰器，frozen=True 表示不可变
class AppConfig:  # 应用配置类，集中管理所有配置项
    """集中保存应用启动时需要的设定资料。"""

    host: str  # 服务器监听的主机地址
    port: int  # 服务器监听的端口号
    debug: bool  # 是否启用调试模式
    static_dir: Path  # 静态文件目录路径
    gemini_api_key: str  # Gemini AI API 密钥
    gemini_model: str  # Gemini AI 模型名称
    auth_token: str | None  # 可选的认证令牌
    max_upload_size: int  # 最大上传文件大小（字节）
    ssl_enabled: bool  # 是否启用 SSL/HTTPS
    ssl_certfile: Path | None  # SSL 证书文件路径（可选）
    ssl_keyfile: Path | None  # SSL 私钥文件路径（可选）


@lru_cache(maxsize=1)  # 使用缓存装饰器，确保只创建一次配置对象（单例模式）
def get_config() -> AppConfig:  # 获取应用配置，返回 AppConfig 对象
    """以单例方式建立并快取设定物件，避免重复解析。"""
    base_dir = Path(__file__).resolve().parent  # 获取当前文件所在目录的绝对路径

    static_dir = Path(os.getenv("STATIC_DIR", "static"))  # 从环境变量读取静态目录，默认 "static"
    if not static_dir.is_absolute():  # 如果路径不是绝对路径
        static_dir = base_dir.parent / static_dir  # 转换为相对于项目根目录的绝对路径

    cert_path = os.getenv("SSL_CERT_FILE")  # 从环境变量读取 SSL 证书文件路径
    key_path = os.getenv("SSL_KEY_FILE")  # 从环境变量读取 SSL 私钥文件路径

    return AppConfig(  # 创建并返回配置对象
        host=os.getenv("HOST", "0.0.0.0"),  # 服务器主机，默认监听所有网络接口
        port=int(os.getenv("PORT", "8080")),  # 服务器端口，默认 8080
        debug=_as_bool(os.getenv("DEBUG"), default=False),  # 调试模式，默认关闭
        static_dir=static_dir,  # 静态文件目录
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),  # Gemini API 密钥，默认空字符串
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),  # Gemini 模型名称，默认 gemini-2.5-flash
        auth_token=os.getenv("AUTH_TOKEN"),  # 认证令牌，可选
        max_upload_size=int(os.getenv("MAX_UPLOAD_SIZE", str(1024 * 1024))),  # 最大上传大小，默认 1MB
        ssl_enabled=_as_bool(os.getenv("SSL_ENABLED"), default=False),  # SSL 是否启用，默认关闭
        ssl_certfile=Path(cert_path).resolve() if cert_path else None,  # SSL 证书文件路径，如果提供则解析为绝对路径
        ssl_keyfile=Path(key_path).resolve() if key_path else None,  # SSL 私钥文件路径，如果提供则解析为绝对路径
    )


def get_local_ip() -> str:  # 获取本机局域网 IP 地址的函数
    """获取本机局域网 IP 地址"""
    try:  # 尝试第一种方法
        # 方法1: 通过连接外部地址获取本机 IP（最可靠）
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:  # 创建 UDP 套接字（IPv4）
            # 连接到一个公网地址（无需可达）以获取本地出口 IP
            s.connect(("8.8.8.8", 80))  # 连接到 Google DNS（不会真正发送数据）
            local_ip = s.getsockname()[0]  # 获取本地套接字的 IP 地址
            if local_ip and local_ip != "0.0.0.0":  # 如果获取到有效 IP 且不是回环地址
                return local_ip  # 返回获取到的 IP
    except Exception:  # 如果方法1失败
        pass  # 忽略异常，继续尝试方法2

    try:  # 尝试第二种方法
        # 方法2: 通过主机名获取 IP
        hostname = socket.gethostname()  # 获取本机主机名
        local_ip = socket.gethostbyname(hostname)  # 通过主机名解析 IP 地址
        if local_ip and local_ip != "0.0.0.0":  # 如果获取到有效 IP 且不是回环地址
            return local_ip  # 返回获取到的 IP
    except Exception:  # 如果方法2也失败
        pass  # 忽略异常，使用默认值

    # 回退到 localhost
    return "0.0.0.0"  # 返回本地回环地址作为默认值


__all__ = ["AppConfig", "get_config", "get_local_ip"]  # 定义模块的公共接口，控制 from module import * 时导入的内容
