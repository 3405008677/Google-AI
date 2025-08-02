# DOM AI - Python AI 应用

这是一个集成了 Gemini AI 和 Web 服务器的 Python 应用程序。

## 🚀 功能特性

### AI 客户端 (`index.py`)
- ✅ 安全的 API 密钥管理（环境变量）
- ✅ 完整的错误处理和异常管理
- ✅ 支持流式和同步内容生成
- ✅ 面向对象的设计
- ✅ 详细的日志记录
- ✅ 类型提示支持

### Web 服务器 (`src/sever.py`)
- ✅ 完整的 HTTP 请求处理
- ✅ RESTful API 端点
- ✅ 静态文件服务
- ✅ 美观的 HTML 界面
- ✅ 完整的错误处理
- ✅ 日志记录
- ✅ 环境变量配置
- ✅ 安全检查

## 📦 安装

1. 克隆项目：
```bash
git clone <repository-url>
cd dom_ai
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 配置环境变量：
```bash
# 复制示例配置文件
cp env.example .env

# 编辑 .env 文件，添加你的 Gemini API 密钥
GEMINI_API_KEY=your_actual_api_key_here
```

## 🔧 使用方法

### 运行 AI 客户端

```bash
python index.py
```

这将启动 Gemini AI 客户端并运行示例测试。

### 运行 Web 服务器

```bash
python src/sever.py
```

服务器将在 `http://localhost:8000` 启动。

## 🌐 API 端点

### GET 端点

- `/` - 首页（美观的 HTML 界面）
- `/api/health` - 健康检查
- `/api/info` - 服务器信息
- `/static/*` - 静态文件服务

### POST 端点

- `/api/echo` - 数据回显（接收 JSON 数据并返回）

## 📁 项目结构

```
dom_ai/
├── index.py              # AI 客户端主文件
├── src/
│   ├── main.py           # 主模块（空文件）
│   └── sever.py          # Web 服务器
├── requirements.txt      # Python 依赖
├── env.example          # 环境变量示例
├── README.md            # 项目说明
└── static/              # 静态文件目录（自动创建）
    └── test.txt         # 示例静态文件
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
from index import GeminiAI

# 创建 AI 客户端
ai_client = GeminiAI()

# 生成内容
response = ai_client.generate_content("解释什么是人工智能")
print(response)
```

### API 调用示例

```bash
# 健康检查
curl http://localhost:8000/api/health

# 服务器信息
curl http://localhost:8000/api/info

# 数据回显
curl -X POST http://localhost:8000/api/echo \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello World"}'
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

## �� 许可证

MIT License 