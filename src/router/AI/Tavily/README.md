# Tavily 搜索服务配置说明

## 简介

Tavily 是一个专为 AI 应用设计的实时搜索 API 服务。本模块将 Tavily 搜索集成到项目中，提供统一的搜索接口。

## 配置步骤

### 1. 安装依赖

```bash
pip install tavily-python
```

或者使用 requirements.txt：

```bash
pip install -r requirements.txt
```

### 2. 获取 API 密钥

1. 访问 [Tavily 官网](https://tavily.com/)
2. 注册账户（可以使用邮箱、Google 或 GitHub 账户）
3. 在账户设置或仪表板中获取 API 密钥
4. 免费计划每月提供 1,000 次 API 调用

### 3. 配置环境变量

在 `.env` 文件中添加：

```bash
TAVILY_API_KEY=your_tavily_api_key_here
```

或者在 `env.example` 中查看示例配置。

## API 接口

### 同步搜索

**端点**: `POST /Tavily/search`

**请求体**:
```json
{
  "text": "搜索关键词"
}
```

**响应**:
```json
{
  "request_id": "xxx",
  "text": "答案: ...\n\n搜索结果:\n1. ...",
  "latency_ms": 1234
}
```

### 流式搜索

**端点**: `POST /Tavily/search/stream`

**请求体**: 同上

**响应**: SSE 流式返回搜索结果

## 使用示例

### Python 示例

```python
import requests

# 同步搜索
response = requests.post(
    "http://localhost:8000/Tavily/search",
    json={"text": "Python 最新版本"}
)
result = response.json()
print(result["text"])
```

### cURL 示例

```bash
curl -X POST "http://localhost:8000/Tavily/search" \
  -H "Content-Type: application/json" \
  -d '{"text": "Python 最新版本"}'
```

## 功能特性

- ✅ 实时网络搜索
- ✅ AI 生成的答案摘要
- ✅ 搜索结果格式化
- ✅ 支持同步和流式返回
- ✅ 访问日志记录

## 目录结构

```
AI/Tavily/
├── models/
│   ├── tavily_client.py      # Tavily 客户端封装
│   └── __init__.py
├── services/
│   ├── search_service.py     # 搜索服务类
│   └── __init__.py
├── api.py                    # 路由定义
├── __init__.py
└── README.md                 # 本文件
```

## 注意事项

1. **API 限制**: 免费计划每月 1,000 次调用，注意控制使用频率
2. **网络延迟**: 搜索需要访问外部 API，响应时间可能较长
3. **错误处理**: 如果 API 密钥无效或网络问题，会返回相应错误信息

## 故障排查

### 问题：导入错误 "tavily-python package not installed"

**解决方案**: 运行 `pip install tavily-python`

### 问题：API 密钥错误

**解决方案**: 
1. 检查 `.env` 文件中的 `TAVILY_API_KEY` 是否正确
2. 确认 API 密钥在 Tavily 官网中有效
3. 检查 API 密钥是否有足够的调用次数

### 问题：搜索超时

**解决方案**: 
- 检查网络连接
- 确认 Tavily 服务是否正常
- 查看日志文件 `log/Tavily.log` 获取详细错误信息

