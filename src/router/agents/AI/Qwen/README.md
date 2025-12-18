# src/router/agents/AI/Qwen 目录

> 通义千问（Qwen）模型适配层，通过 DashScope API 接入。

---

## 概述

接入阿里云 DashScope API，支持 Qwen 系列模型（Turbo、Plus、Max）。

---

## 配置

```ini
# .env
QWEN_API_KEY=your_dashscope_api_key

# 模型选择
QWEN_MODEL=qwen-plus             # 推荐，性价比高
# QWEN_MODEL=qwen-turbo          # 更快，适合简单任务
# QWEN_MODEL=qwen-max            # 最强，适合复杂任务

# API 地址（默认 DashScope）
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# 请求配置
QWEN_TIMEOUT=60                  # 超时时间（秒）
QWEN_MAX_RETRIES=3               # 最大重试次数
```

---

## 可用模型

| 模型 | 特点 | 适用场景 |
|:---|:---|:---|
| `qwen-turbo` | 快速、经济 | 简单问答、日常对话 |
| `qwen-plus` | 均衡、推荐 | 通用场景 |
| `qwen-max` | 最强能力 | 复杂推理、专业任务 |
| `qwen-max-longcontext` | 长上下文 | 长文档分析 |

---

## API Key 获取

1. 访问 [阿里云 DashScope](https://dashscope.console.aliyun.com/)
2. 注册/登录阿里云账号
3. 开通 DashScope 服务
4. 创建 API Key
5. 将 Key 配置到 `.env`

---

## 使用示例

```python
from src.router.agents.AI.Qwen import create_qwen_llm

# 创建 LLM 实例
llm = create_qwen_llm(temperature=0.7)

# 调用
from langchain_core.messages import HumanMessage
response = await llm.ainvoke([HumanMessage(content="你好")])
print(response.content)
```

---

## OpenAI 兼容模式

DashScope 提供 OpenAI 兼容接口，本项目使用此模式：

```python
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model=settings.QWEN_MODEL,
    openai_api_key=settings.QWEN_API_KEY,
    openai_api_base=settings.QWEN_BASE_URL,
)
```

---

## 注意事项

1. **计费**：按 Token 计费，注意监控用量。
2. **并发限制**：有 QPS 限制，高并发场景需申请提升。
3. **上下文长度**：不同模型支持的最大上下文不同。
