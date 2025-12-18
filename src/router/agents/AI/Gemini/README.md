# src/router/agents/AI/Gemini 目录

> Google Gemini 模型适配层。

---

## 概述

接入 Google Gemini API，支持 Gemini Pro、Gemini 1.5 Flash/Pro 等模型。

---

## 配置

```ini
# .env
GEMINI_API_KEY=your_google_api_key

# 模型选择
GEMINI_MODEL=gemini-1.5-flash    # 推荐，速度快，性价比高
# GEMINI_MODEL=gemini-1.5-pro    # 更强大，适合复杂任务
# GEMINI_MODEL=gemini-pro        # 经典版本

# 请求配置
GEMINI_TIMEOUT=60                # 超时时间（秒）
GEMINI_MAX_RETRIES=3             # 最大重试次数
```

---

## 可用模型

| 模型 | 特点 | 适用场景 |
|:---|:---|:---|
| `gemini-1.5-flash` | 快速、经济 | 日常对话、简单任务 |
| `gemini-1.5-pro` | 强大、多模态 | 复杂推理、长文本 |
| `gemini-pro` | 经典、稳定 | 通用场景 |

---

## API Key 获取

1. 访问 [Google AI Studio](https://makersuite.google.com/)
2. 登录 Google 账号
3. 创建 API Key
4. 将 Key 配置到 `.env`

---

## 使用示例

```python
from src.router.agents.AI.Gemini import create_gemini_llm

# 创建 LLM 实例
llm = create_gemini_llm(temperature=0.7)

# 调用
from langchain_core.messages import HumanMessage
response = await llm.ainvoke([HumanMessage(content="你好")])
print(response.content)
```

---

## 注意事项

1. **地区限制**：部分地区可能需要代理访问。
2. **速率限制**：免费版有 QPM（每分钟请求数）限制。
3. **多模态**：Gemini 1.5 支持图片输入，需使用对应的消息格式。
