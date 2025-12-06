# 全能调度系统 (Orchestrator)

## 简介

全能调度系统是一个智能任务分配系统，能够自动判断用户意图，并将任务分配给最合适的服务：

- **聊天 (chat)**: 使用 SelfHosted 模型进行普通对话
- **搜索 (search)**: 使用 Tavily 进行网络搜索
- **数据库 (database)**: 查询数据库（开发中）

## 工作原理

```
用户请求
    ↓
意图分类器 (使用 SelfHosted 模型)
    ↓
判断意图类型
    ↓
    ├─→ chat → SelfHosted 模型
    ├─→ search → Tavily 搜索
    └─→ database → 数据库服务（待实现）
    ↓
返回结果
```

## API 接口

### 同步请求

**端点**: `POST /Orchestrator/chat`

**请求体**:
```json
{
  "text": "用户的问题或请求"
}
```

**响应**:
```json
{
  "request_id": "xxx",
  "text": "[意图: chat|search|database | 置信度: 0.95]\n\n响应内容...",
  "latency_ms": 1234
}
```

### 流式请求

**端点**: `POST /Orchestrator/chat/stream`

**请求体**: 同上

**响应**: SSE 流式返回

## 意图判断规则

### 1. Chat (普通聊天)
- 日常对话、问答、闲聊
- 情感交流
- 不需要外部信息的对话
- 技术问答（可以使用已有知识回答）

**示例**:
- "你好，最近怎么样？"
- "Python如何读取文件？"
- "给我讲个笑话"

### 2. Search (网络搜索)
- 需要获取最新信息
- 实时数据、新闻
- 技术文档、产品信息
- 当前事件、趋势

**示例**:
- "今天天气怎么样？"
- "最新的Python 3.12有什么新特性？"
- "最近有什么科技新闻？"

### 3. Database (数据库查询)
- 明确提到查询数据库
- 查找记录、统计数据
- 业务数据查询

**示例**:
- "查询用户表中ID为123的记录"
- "统计今天的订单数量"
- "查找所有未付款的订单"

## 使用示例

### Python 示例

```python
import requests

# 普通聊天
response = requests.post(
    "http://localhost:8000/Orchestrator/chat",
    json={"text": "你好，最近怎么样？"}
)
print(response.json()["text"])

# 需要搜索的问题
response = requests.post(
    "http://localhost:8000/Orchestrator/chat",
    json={"text": "最新的Python版本是什么？"}
)
print(response.json()["text"])

# 数据库查询
response = requests.post(
    "http://localhost:8000/Orchestrator/chat",
    json={"text": "查询用户表中ID为123的记录"}
)
print(response.json()["text"])
```

### cURL 示例

```bash
# 普通聊天
curl -X POST "http://localhost:8000/Orchestrator/chat" \
  -H "Content-Type: application/json" \
  -d '{"text": "你好，最近怎么样？"}'

# 搜索
curl -X POST "http://localhost:8000/Orchestrator/chat" \
  -H "Content-Type: application/json" \
  -d '{"text": "最新的Python版本是什么？"}'
```

## 配置要求

### 必需的服务

1. **SelfHosted 模型**: 用于意图分类和普通聊天
   - 需要配置 `SELF_MODEL_BASE_URL` 和 `SELF_MODEL_NAME`

2. **Tavily 搜索**: 用于网络搜索
   - 需要配置 `TAVILY_API_KEY`

### 可选服务

3. **数据库服务**: 待实现
   - 需要配置数据库连接信息

## 目录结构

```
AI/Orchestrator/
├── services/
│   ├── intent_classifier.py    # 意图分类器
│   ├── orchestrator_service.py # 调度服务
│   └── __init__.py
├── api.py                      # 路由定义
├── __init__.py
└── README.md                   # 本文件
```

## 扩展开发

### 添加新的意图类型

1. 在 `intent_classifier.py` 的 `IntentType` 枚举中添加新类型
2. 更新系统提示词，添加新类型的说明
3. 在 `orchestrator_service.py` 中添加对应的服务调用逻辑

### 实现数据库服务

1. 创建 `AI/Database/` 目录结构
2. 实现数据库查询服务
3. 在 `orchestrator_service.py` 中导入并调用

示例：
```python
from ...Database.services.database_service import DatabaseService

# 在 __init__ 中初始化
self.database_service = DatabaseService()

# 在 generate_response 中调用
elif intent == IntentType.DATABASE.value:
    response = await self.database_service.query(request)
```

## 日志

访问日志保存在 `log/Orchestrator.log`，包含：
- 用户查询
- 意图判断结果
- 路由到的服务
- 响应时间

## 注意事项

1. **意图判断准确性**: 依赖 SelfHosted 模型的能力，可以通过优化系统提示词提高准确性
2. **性能**: 意图判断会增加一次模型调用，但能确保任务分配给最合适的服务
3. **错误处理**: 如果意图判断失败，会使用基于关键词的备用分类方法
4. **置信度**: 系统会返回意图判断的置信度，可以用于后续优化

