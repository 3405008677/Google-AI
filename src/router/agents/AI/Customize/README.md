# src/router/agents/AI/Customize 目录

> 自定义模型适配层，支持任何 OpenAI 兼容接口。

---

## 概述

接入自建模型或第三方 OpenAI 兼容服务，如：
- 本地部署的 LLM（vLLM、Ollama、LocalAI）
- 其他云服务（DeepSeek、Moonshot、智谱等）

---

## 配置

```ini
# .env

# 基础配置
SELF_MODEL_BASE_URL=http://localhost:8000/v1   # API 地址
SELF_MODEL_NAME=my-model                        # 模型名称
SELF_MODEL_API_KEY=                            # API Key（可选）

# 请求配置
SELF_MODEL_TIMEOUT=60                           # 超时时间
SELF_MODEL_MAX_RETRIES=3                        # 最大重试次数
```

---

## 使用场景

### 1. 本地 vLLM

```ini
SELF_MODEL_BASE_URL=http://localhost:8000/v1
SELF_MODEL_NAME=Qwen/Qwen2-7B-Instruct
SELF_MODEL_API_KEY=
```

### 2. Ollama

```ini
SELF_MODEL_BASE_URL=http://localhost:11434/v1
SELF_MODEL_NAME=llama3
SELF_MODEL_API_KEY=ollama
```

### 3. DeepSeek

```ini
SELF_MODEL_BASE_URL=https://api.deepseek.com/v1
SELF_MODEL_NAME=deepseek-chat
SELF_MODEL_API_KEY=your_deepseek_key
```

### 4. Moonshot (Kimi)

```ini
SELF_MODEL_BASE_URL=https://api.moonshot.cn/v1
SELF_MODEL_NAME=moonshot-v1-8k
SELF_MODEL_API_KEY=your_moonshot_key
```

### 5. 智谱 GLM

```ini
SELF_MODEL_BASE_URL=https://open.bigmodel.cn/api/paas/v4
SELF_MODEL_NAME=glm-4
SELF_MODEL_API_KEY=your_zhipu_key
```

---

## 使用示例

```python
from src.router.agents.AI.Customize import create_customize_llm

# 创建 LLM 实例
llm = create_customize_llm(temperature=0.7)

# 调用
from langchain_core.messages import HumanMessage
response = await llm.ainvoke([HumanMessage(content="你好")])
print(response.content)
```

---

## 接口要求

自定义模型需兼容 OpenAI API 格式：

### Chat Completions

```
POST {base_url}/chat/completions

{
  "model": "model_name",
  "messages": [
    {"role": "user", "content": "你好"}
  ],
  "temperature": 0.7
}
```

### 响应格式

```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "你好！有什么可以帮助你的？"
      }
    }
  ]
}
```

---

## 优先级

自定义模型在 `llm_factory` 中具有最高优先级：

```
Customize (最高) > Qwen > Gemini (最低)
```

如果配置了 `SELF_MODEL_BASE_URL`，将优先使用自定义模型。

---

## 注意事项

1. **健康检查**：确保模型服务可访问。
2. **超时设置**：本地模型可能需要更长超时。
3. **API 兼容性**：确保模型服务完整支持 OpenAI Chat API。
