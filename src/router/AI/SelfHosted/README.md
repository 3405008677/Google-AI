# SelfHosted 智能聊天服务

## 简介

SelfHosted 服务现在集成了智能调度功能，作为统一入口。所有请求都会：

1. **自动判断用户意图**（使用 SelfHosted 模型）
2. **根据意图准备上下文**：
   - **搜索意图**: 先调用 Tavily 搜索，将结果作为上下文
   - **数据库意图**: 先查询数据库，将结果作为上下文
   - **聊天意图**: 直接使用原请求
3. **统一通过 SelfHosted 模型处理并返回**

## 工作流程

```
用户请求 → SelfHosted/chat/stream
    ↓
智能调度系统（Orchestrator）
    ↓
判断意图
    ↓
    ├─→ chat → 直接使用 SelfHosted 模型
    ├─→ search → Tavily 搜索 → 结果作为上下文 → SelfHosted 模型处理
    └─→ database → 数据库查询 → 结果作为上下文 → SelfHosted 模型处理
    ↓
SelfHosted 模型筛选/总结
    ↓
返回给前端
```

## API 接口

### 同步请求

**端点**: `POST /SelfHosted/chat`

**请求体**:
```json
{
  "text": "今天是什么日子？"
}
```

**处理流程**:
1. 判断意图：发现是搜索意图（需要获取当前日期信息）
2. 调用 Tavily 搜索："今天是什么日子"
3. 将搜索结果作为上下文给 SelfHosted 模型
4. SelfHosted 模型根据搜索结果生成回答
5. 返回给前端

**响应**:
```json
{
  "request_id": "xxx",
  "text": "今天是2024年12月6日，星期五...",
  "latency_ms": 2345
}
```

### 流式请求

**端点**: `POST /SelfHosted/chat/stream`

**请求体**: 同上

**响应**: SSE 流式返回，SelfHosted 模型会逐步生成回答

## 使用示例

### 示例 1: 普通聊天

```bash
curl -X POST "http://localhost:8000/SelfHosted/chat" \
  -H "Content-Type: application/json" \
  -d '{"text": "你好，最近怎么样？"}'
```

**流程**: 判断为聊天意图 → 直接使用 SelfHosted 模型 → 返回回答

### 示例 2: 需要搜索的问题

```bash
curl -X POST "http://localhost:8000/SelfHosted/chat" \
  -H "Content-Type: application/json" \
  -d '{"text": "今天是什么日子？"}'
```

**流程**: 
1. 判断为搜索意图
2. 调用 Tavily 搜索："今天是什么日子"
3. 获取搜索结果（当前日期、节日等信息）
4. 将搜索结果作为上下文给 SelfHosted 模型
5. SelfHosted 模型根据搜索结果生成回答
6. 返回给前端

### 示例 3: 数据库查询（待实现）

```bash
curl -X POST "http://localhost:8000/SelfHosted/chat" \
  -H "Content-Type: application/json" \
  -d '{"text": "查询用户表中ID为123的记录"}'
```

**流程**:
1. 判断为数据库意图
2. 查询数据库
3. 将查询结果作为上下文给 SelfHosted 模型
4. SelfHosted 模型格式化并返回结果

## 优势

1. **统一入口**: 用户只需要访问 `/SelfHosted/chat`，系统自动判断需要什么服务
2. **智能整合**: 搜索结果经过 AI 筛选和总结，而不是直接返回原始搜索结果
3. **无缝体验**: 用户感觉就像在和 AI 对话，AI 会自动帮用户搜索和查询
4. **灵活扩展**: 可以轻松添加新的意图类型和服务

## 配置要求

### 必需配置

1. **SelfHosted 模型**: 
   - `SELF_MODEL_BASE_URL`: 模型服务地址
   - `SELF_MODEL_NAME`: 模型名称

2. **Tavily 搜索** (用于搜索意图):
   - `TAVILY_API_KEY`: Tavily API 密钥

### 可选配置

3. **数据库服务** (用于数据库意图，待实现):
   - 数据库连接配置

## 日志

所有请求的日志保存在 `log/SelfHosted.log`，包含：
- 用户查询
- 意图判断结果
- 调用的服务（搜索/数据库）
- 最终响应

## 注意事项

1. **意图判断**: 依赖 SelfHosted 模型的能力，可以通过优化提示词提高准确性
2. **性能**: 搜索意图会增加一次搜索 API 调用，但能提供更准确的信息
3. **错误处理**: 如果搜索失败，SelfHosted 模型会告知用户无法获取信息
4. **上下文长度**: 搜索结果会作为上下文，注意不要超过模型的上下文限制

