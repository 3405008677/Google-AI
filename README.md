# DOM AI - Python AI 应用

这是一个集成了 Gemini AI 和 Web 服务器的 Python 应用程序。

## 🚀 功能特性

### Gemini 模块 (`src/modules/gemini_client.py`)
- ✅ 集中管理 API Key、模型等配置
- ✅ 同步与流式输出封装
- ✅ 统一错误处理与类型提示
- ✅ 单例客户端，避免重复初始化

### Web 服务器 (`src/server/index.py`)
- ✅ FastAPI + Uvicorn 一键启动
- ✅ RESTful / SSE API 端点
- ✅ 静态文件服务与基础安全检查
- ✅ 日志 + `.env` 配置管理
- ✅ 可选 SSL / HTTPS 支援

## 📦 安装

1. 克隆项目：
```bash
git clone <repository-url>
cd dom_ai
```

2. 安装依赖：
```bash
pip install -r requirements.txt
或者
python -m pip install -r requirements.txt
```

3. 配置环境变量：
```bash
# 复制示例配置文件
cp env.example .env

# 编辑 .env 文件，添加你的 Gemini API 密钥
GEMINI_API_KEY=your_actual_api_key_here
```

## 🔧 使用方法

### 启动服务

```bash
python -m src.main
```

服务器会在 `.env` 设置的 `HOST:PORT` 启动（默认 `http://localhost:8000`）。

## 🌐 API 端点

- `/api/home` - 示例回传
- `/api/google-ai/content` - 同步生成 Gemini 内容（返回 JSON，含请求 ID 与耗时）
- `/api/google-ai/stream` - 以 `text/event-stream` 方式串流 Gemini 回复（新增 request_id、结束事件）
- `/static/*` - 静态文件

## 📁 项目结构

```
google-ai/
├── src/
│   ├── config.py             # 环境/运行配置
│   ├── main.py               # 入口，启动 FastAPI
│   ├── modules/
│   │   └── gemini_client.py  # Gemini 客户端封装
│   ├── router/
│   │   ├── index.py          # 汇总各子路由
│   │   └── googleAI/         # Gemini API 路由
│   └── server/
│       └── index.py          # FastAPI + Uvicorn 服务
├── env.example               # 环境变量示例
├── requirements.txt          # 依赖
└── README.md
```

## 🔒 安全特性

- API 密钥通过环境变量管理
- 防止目录遍历攻击
- 输入验证和清理
- 错误信息不暴露敏感数据

## 🛠️ 配置选项

### 环境变量

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `GEMINI_API_KEY` | 必需 | Gemini AI API 密钥 |
| `PORT` | 8000 | 服务器端口 |
| `HOST` | 0.0.0.0 | 服务器主机 |
| `DEBUG` | False | 调试模式 |
| `STATIC_DIR` | static | 静态文件目录 |

## 📝 示例用法

### Python 代码示例

```python
from src.modules.gemini_client import get_gemini_client

client = get_gemini_client()
print(client.generate_text("解释什么是人工智能"))
```

### API 调用示例

```bash
# 同步生成（可带系统提示 / 历史对话）
curl -X POST http://localhost:8000/api/google-ai/content \
  -H "Content-Type: application/json" \
  -d '{
        "text":"介绍一下 FastAPI",
        "system_prompt":"你是一个资深 Python 教练",
        "history":[{"role":"user","content":"你好"}]
      }'

# 串流（SSE）
curl -N -X POST http://localhost:8000/api/google-ai/stream \
  -H "Content-Type: application/json" \
  -d '{"text":"给我一首短诗"}'
```

## 🐛 故障排除

### 常见问题

1. **API 密钥错误**
   - 确保在 `.env` 文件中设置了正确的 `GEMINI_API_KEY`
   - 检查 API 密钥是否有效

2. **端口被占用**
   - 修改 `.env` 文件中的 `PORT` 值
   - 或者停止占用该端口的其他服务

3. **权限错误**
   - 确保有足够的权限创建文件和目录
   - 检查防火墙设置

### 日志文件

服务器运行时会生成 `server.log` 文件，包含详细的运行日志。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License 