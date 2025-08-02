import sys
import os


# 获取项目根目录（dom_ai/，即 src/ 的父目录）
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(root_dir)

# 获取项目根目录的绝对路径（main.py所在的目录）
# current_dir = os.path.dirname(os.path.abspath(__file__))
# 将当前目录添加到 Python 路径中，这样可以导入同级目录下的模块
# sys.path.append(current_dir)

from src.server import initServer, app

# 启动服务器
initServer()
